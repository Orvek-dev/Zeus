from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zeus_agent.connector_runtime.lifecycle import ConnectorLifecycleRegistry
from zeus_agent.kernel.authority import AuthorityContext
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError
from zeus_agent.transport_runtime import (
    TransportExecutionGate,
    TransportExecutionGateRequest,
    TransportKind,
    TransportRegistry,
)

_BROKER_DECISIONS: Final[dict[str, Literal["allowed", "blocked", "error"]]] = {
    "allowed": "allowed",
    "blocked": "blocked",
    "error": "error",
}


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class ConnectorExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str
    payload: dict[str, str] = Field(default_factory=dict)
    credential_scope: Optional[str] = None
    dry_run: bool = True

    @field_validator("capability_id")
    @classmethod
    def _validate_capability_id(cls, value: str) -> str:
        return _require_non_empty(value, "capability_id")

    @field_validator("credential_scope")
    @classmethod
    def _validate_credential_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "credential_scope")


class ConnectorExecutionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_id: str
    connector_kind: Literal["mcp", "api", "plugin"]
    capability_id: str
    transport: Literal["dry_run"] = "dry_run"
    dry_run: bool = True
    credential_scope_label: Optional[str] = None
    side_effects: bool = False


class ConnectorExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["allowed", "blocked", "error"]
    handler_executed: bool
    envelope: Optional[ConnectorExecutionEnvelope] = None
    reason: Optional[str] = None
    broker_response: Optional[dict[str, object]] = None
    redacted_input: Optional[str] = None


class ConnectorExecutionRuntime:
    def __init__(
        self,
        registry: ConnectorLifecycleRegistry,
        transport_registry: Optional[TransportRegistry] = None,
    ) -> None:
        self._registry = registry
        self._transport_gate = (
            TransportExecutionGate(transport_registry)
            if transport_registry is not None
            else None
        )

    def execute(
        self,
        request: ConnectorExecutionRequest,
        authority: AuthorityContext,
    ) -> ConnectorExecutionResult:
        binding = self._registry.capability_binding(request.capability_id)
        if binding is None:
            return _blocked_result(reason="unknown_connector_capability")
        if not request.dry_run:
            return _blocked_result(reason="live_transport_not_authorized")

        credential_result = _credential_scope_label(request.credential_scope)
        if credential_result.decision == "blocked":
            return _blocked_result(
                reason=credential_result.reason or "credential_scope_invalid",
                redacted_input=credential_result.redacted_input,
            )

        if self._transport_gate is not None:
            gate = self._transport_gate.evaluate(
                TransportExecutionGateRequest(
                    capability_id=binding.capability_id,
                    transport_kind=TransportKind(binding.kind.value),
                    credential_scope=credential_result.label,
                ),
                authority,
            )
            if gate.decision == "blocked":
                return _blocked_result(
                    reason=gate.reason,
                    redacted_input=gate.redacted_input,
                )

        handler_executed = {"value": False}
        handlers = self._registry.build_stub_handlers()
        handlers[request.capability_id] = _execution_handler(
            connector_id=binding.connector_id,
            connector_kind=binding.kind.value,
            capability_id=binding.capability_id,
            credential_scope_label=credential_result.label,
            handler_executed=handler_executed,
        )
        payload = dict(request.payload)
        if credential_result.label is not None:
            payload["credential_scope"] = credential_result.label

        broker = CapabilityBroker(
            graph=self._registry.build_capability_graph(),
            handlers=handlers,
        )
        broker_response = broker.dispatch(
            capability_id=request.capability_id,
            payload=payload,
            context=authority,
            criterion_id="REQ-ZEUS-WAVE5-004:S1",
        )
        envelope = _envelope_from_response(broker_response.get("result"))
        return ConnectorExecutionResult(
            decision=_decision_from_response(broker_response),
            reason=_reason_from_response(broker_response),
            handler_executed=handler_executed["value"],
            envelope=envelope,
            broker_response=broker_response,
        )


class _CredentialScopeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["allowed", "blocked"]
    label: Optional[str] = None
    reason: Optional[str] = None
    redacted_input: Optional[str] = None


def _credential_scope_label(raw_value: Optional[str]) -> _CredentialScopeResult:
    if raw_value is None:
        return _CredentialScopeResult(decision="allowed")
    try:
        scope = CredentialScope.parse(raw_value)
    except CredentialScopeUnsafeError as exc:
        return _CredentialScopeResult(
            decision="blocked",
            reason=exc.payload["reason"],
            redacted_input=exc.payload["redacted"],
        )
    except ValueError as exc:
        return _CredentialScopeResult(decision="blocked", reason=str(exc))
    return _CredentialScopeResult(decision="allowed", label=scope.label)


def _execution_handler(
    *,
    connector_id: str,
    connector_kind: str,
    capability_id: str,
    credential_scope_label: Optional[str],
    handler_executed: dict[str, bool],
) -> object:
    def handler(payload: dict[str, object]) -> dict[str, object]:
        del payload
        handler_executed["value"] = True
        return ConnectorExecutionEnvelope(
            connector_id=connector_id,
            connector_kind=connector_kind,
            capability_id=capability_id,
            credential_scope_label=credential_scope_label,
        ).model_dump(mode="json")

    return handler


def _envelope_from_response(result: object) -> ConnectorExecutionEnvelope | None:
    if result is None:
        return None
    return ConnectorExecutionEnvelope.model_validate(result)


def _decision_from_response(
    broker_response: dict[str, object],
) -> Literal["allowed", "blocked", "error"]:
    decision = broker_response.get("decision")
    if not isinstance(decision, str):
        return "error"
    return _BROKER_DECISIONS.get(decision, "error")


def _reason_from_response(broker_response: dict[str, object]) -> Optional[str]:
    reason = broker_response.get("reason")
    if isinstance(reason, str):
        return reason
    return None


def _blocked_result(
    *,
    reason: str,
    redacted_input: Optional[str] = None,
) -> ConnectorExecutionResult:
    return ConnectorExecutionResult(
        decision="blocked",
        reason=reason,
        handler_executed=False,
        redacted_input=redacted_input,
    )
