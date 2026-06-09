from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

from zeus_agent.governed_live_slice_runtime.models import GovernedLiveSliceResult

ConnectorPlatformDecision = Literal["ready", "blocked"]
ConnectorPlatformScenario = Literal["status", "trusted-local-smoke", "public-boundary"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class GovernedLiveConnectorPlatformResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ConnectorPlatformDecision
    target_version: Literal["v5.8.0"] = "v5.8.0"
    scenario: ConnectorPlatformScenario
    surfaces: tuple[str, ...]
    allowed_surfaces: tuple[str, ...] = ()
    blocked_surfaces: tuple[str, ...] = ()
    connector_results: tuple[GovernedLiveSliceResult, ...] = ()
    connectors_ready: bool = False
    provider_connector_ready: bool = False
    mcp_connector_ready: bool = False
    gateway_connector_ready: bool = False
    local_sandbox_connector_ready: bool = False
    broker_evidence_required: bool = True
    broker_evidence_bound_count: int = 0
    missing_requirement_count: int = 0
    handler_executed_count: int = 0
    production_ready: bool = False
    network_opened: bool = False
    credential_material_accessed: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    @field_validator("surfaces", "allowed_surfaces", "blocked_surfaces")
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: object) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
