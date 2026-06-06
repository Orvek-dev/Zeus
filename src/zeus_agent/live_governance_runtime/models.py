from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

LiveGovernanceDecision = Literal["allowed", "blocked"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class LiveCapability(BaseModel):
    model_config = _MODEL_CONFIG

    capability_id: str
    provider: str
    scenario: str
    lease_required: bool = True
    approval_required: bool = True
    promotion_guard_required: bool = True
    broker_evidence_required: bool = True
    lease_ref: str
    approval_ref: str
    promotion_guard_ref: str
    broker_evidence_ref: str
    credential_scope: str
    network_hosts: tuple[str, ...] = ()

    @field_validator(
        "capability_id",
        "provider",
        "scenario",
        "lease_ref",
        "approval_ref",
        "promotion_guard_ref",
        "broker_evidence_ref",
        "credential_scope",
    )
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("network_hosts")
    @classmethod
    def _validate_network_hosts(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, "network_hosts") for value in values)


class GovernedLiveRequest(BaseModel):
    model_config = _MODEL_CONFIG

    provider: str
    capability_id: str
    scenario: str
    lease_ref: Optional[str]
    approval_ref: Optional[str]
    promotion_guard_ref: Optional[str]
    broker_evidence_ref: Optional[str]
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    raw_credential: Optional[str] = None

    @field_validator(
        "provider",
        "capability_id",
        "scenario",
        "lease_ref",
        "approval_ref",
        "promotion_guard_ref",
        "broker_evidence_ref",
        "credential_scope",
        "network_host",
        "raw_credential",
    )
    @classmethod
    def _validate_optional_text(cls, value: Optional[str], info: object) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)


class GovernedLiveResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGovernanceDecision
    capability_id: str
    blocked_reasons: tuple[str, ...] = ()
    handler_executed: bool = False
    lease_bound: bool = False
    approval_bound: bool = False
    promotion_guard_bound: bool = False
    broker_evidence_bound: bool = False
    no_secret_echo: bool = True
    raw_secret_returned: bool = False
    network_opened: bool = False
    credential_material_accessed: bool = False
    external_delivery_opened: bool = False
    live_production_claimed: bool = False
    broker_decision: Optional[str] = None
    broker_evidence_status: Optional[str] = None
    broker_evidence_type: Optional[str] = None

    @field_validator(
        "capability_id",
        "broker_decision",
        "broker_evidence_status",
        "broker_evidence_type",
    )
    @classmethod
    def _validate_optional_text(cls, value: Optional[str], info: object) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)

    @field_validator("blocked_reasons")
    @classmethod
    def _validate_reasons(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, "blocked_reasons") for value in values)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
