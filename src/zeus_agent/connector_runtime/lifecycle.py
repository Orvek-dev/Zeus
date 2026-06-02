from __future__ import annotations

from enum import Enum
from typing import Callable, Optional, Sequence

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityHealth,
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class ConnectorKind(str, Enum):
    mcp = "mcp"
    api = "api"
    plugin = "plugin"


class ConnectorLifecycleState(str, Enum):
    registered = "registered"
    healthy = "healthy"
    unhealthy = "unhealthy"
    disabled = "disabled"


class ConnectorDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_id: str
    kind: ConnectorKind
    display_name: str
    descriptors: tuple[CapabilityDescriptor, ...]

    @field_validator("connector_id", "display_name")
    @classmethod
    def _validate_required_fields(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("descriptors")
    @classmethod
    def _validate_descriptors(
        cls,
        descriptors: tuple[CapabilityDescriptor, ...],
    ) -> tuple[CapabilityDescriptor, ...]:
        if not descriptors:
            raise ValueError("descriptors must be non-empty")
        return descriptors


class _ConnectorEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    declaration: ConnectorDeclaration
    state: ConnectorLifecycleState


class ConnectorCapabilityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_id: str
    kind: ConnectorKind
    capability_id: str
    state: ConnectorLifecycleState


StubHandler = Callable[[dict[str, object]], dict[str, object]]


class ConnectorLifecycleRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, _ConnectorEntry] = {}

    def register(self, declaration: ConnectorDeclaration) -> None:
        existing = self._entries.get(declaration.connector_id)
        if existing is not None:
            self._entries[declaration.connector_id] = existing.model_copy(
                update={
                    "declaration": declaration,
                    "state": ConnectorLifecycleState.registered,
                }
            )
            return
        self._entries[declaration.connector_id] = _ConnectorEntry(
            declaration=declaration,
            state=ConnectorLifecycleState.registered,
        )

    def set_state(self, connector_id: str, state: ConnectorLifecycleState) -> None:
        connector_id_value = _require_non_empty(connector_id, "connector_id")
        entry = self._entries.get(connector_id_value)
        if entry is None:
            raise ValueError("unknown connector_id: {0}".format(connector_id_value))
        self._entries[connector_id_value] = entry.model_copy(update={"state": state})

    def set_health(self, connector_id: str, *, healthy: bool) -> None:
        self.set_state(
            connector_id,
            ConnectorLifecycleState.healthy if healthy else ConnectorLifecycleState.unhealthy,
        )

    def discovered_tool_names(self) -> list[str]:
        names = []
        for entry in self._entries.values():
            for descriptor in entry.declaration.descriptors:
                names.append(descriptor.name)
        return sorted(names)

    def lifecycle_report(self) -> dict[str, str]:
        return {
            connector_id: entry.state.value
            for connector_id, entry in self._entries.items()
        }

    def capability_binding(
        self,
        capability_id: str,
    ) -> ConnectorCapabilityBinding | None:
        capability_id_value = _require_non_empty(capability_id, "capability_id")
        for entry in self._entries.values():
            for descriptor in entry.declaration.descriptors:
                if descriptor.capability_id == capability_id_value:
                    return ConnectorCapabilityBinding(
                        connector_id=entry.declaration.connector_id,
                        kind=entry.declaration.kind,
                        capability_id=descriptor.capability_id,
                        state=entry.state,
                    )
        return None

    def build_capability_graph(self) -> CapabilityGraph:
        return _LiveConnectorCapabilityGraph(self)

    def _live_descriptors(self, *, include_disabled: bool) -> list[CapabilityDescriptor]:
        descriptors = []
        for entry in self._entries.values():
            if entry.state == ConnectorLifecycleState.disabled and not include_disabled:
                continue
            descriptor_health = self._descriptor_health(entry.state)
            for descriptor in entry.declaration.descriptors:
                descriptors.append(descriptor.model_copy(update={"health": descriptor_health}))
        return descriptors

    def build_stub_handlers(self) -> dict[str, StubHandler]:
        handlers: dict[str, StubHandler] = {}
        for entry in self._entries.values():
            connector_id = entry.declaration.connector_id
            for descriptor in entry.declaration.descriptors:
                handlers[descriptor.capability_id] = self._build_stub_handler(
                    connector_id=connector_id,
                    capability_id=descriptor.capability_id,
                )
        return handlers

    @staticmethod
    def _descriptor_health(state: ConnectorLifecycleState) -> CapabilityHealth:
        if state == ConnectorLifecycleState.healthy:
            return CapabilityHealth.healthy
        return CapabilityHealth.unhealthy

    @staticmethod
    def _build_stub_handler(connector_id: str, capability_id: str) -> StubHandler:
        connector_id_value = _require_non_empty(connector_id, "connector_id")
        capability_id_value = _require_non_empty(capability_id, "capability_id")

        def handler(payload: dict[str, object]) -> dict[str, object]:
            del payload
            return {
                "connector_id": connector_id_value,
                "capability_id": capability_id_value,
                "side_effects": False,
            }

        return handler


ConnectorLifecycleRuntime = ConnectorLifecycleRegistry


class _LiveConnectorCapabilityGraph(CapabilityGraph):
    def __init__(self, registry: ConnectorLifecycleRegistry) -> None:
        self._registry = registry
        super().__init__(registry._live_descriptors(include_disabled=True))

    def compile_model_schema(
        self,
        profile: str,
        authority: AuthorityContext,
        approval_receipts: Optional[Sequence[ApprovalReceipt]] = None,
        include_unhealthy: bool = False,
    ) -> list[dict[str, object]]:
        return CapabilityGraph(
            self._registry._live_descriptors(include_disabled=False)
        ).compile_model_schema(
            profile=profile,
            authority=authority,
            approval_receipts=approval_receipts,
            include_unhealthy=include_unhealthy,
        )

    def descriptor_for(self, capability_id: str) -> CapabilityDescriptor | None:
        for descriptor in self._registry._live_descriptors(include_disabled=True):
            if descriptor.capability_id == capability_id:
                return descriptor
        return None
