from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.transport_runtime.manifest import TransportHealth


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class SandboxProbeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_id: str
    transport_id: str
    expected_health: TransportHealth

    @field_validator("probe_id", "transport_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)


class ProbeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_id: str
    transport_id: str
    health: TransportHealth
    handler_executed: bool = False
    network_opened: bool = False
    side_effects: bool = False

    @field_validator("probe_id", "transport_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)
