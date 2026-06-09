from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

GovernedLiveSliceDecision = Literal["allowed", "blocked", "report"]
GovernedLiveSurface = Literal["provider", "mcp", "gateway", "local_sandbox"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class GovernedLiveSliceResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: GovernedLiveSliceDecision
    target_version: Literal["v4.5.0"] = "v4.5.0"
    surface: GovernedLiveSurface
    capability_id: str
    scenario: str
    blocked_reasons: tuple[str, ...] = ()
    required_requirements: tuple[str, ...] = (
        "objective_run_id",
        "lease_ref",
        "approval_ref",
        "promotion_guard_ref",
        "broker_evidence_ref",
        "credential_scope",
        "sandbox_policy_ref",
        "audit_receipt_ref",
    )
    missing_requirements: tuple[str, ...] = ()
    operator_next_steps: tuple[str, ...] = ()
    live_preflight_requirement_map_available: bool = True
    authority_ux_runtime_available: bool = True
    trusted_loopback_live_smoke_available: bool = False
    governed_live_slice_ready: bool = True
    lease_bound: bool = False
    approval_bound: bool = False
    promotion_guard_bound: bool = False
    broker_evidence_bound: bool = False
    broker_decision: Optional[str] = None
    broker_evidence_status: Optional[str] = None
    broker_evidence_type: Optional[str] = None
    no_secret_echo: bool = True
    raw_secret_returned: bool = False
    network_opened: bool = False
    credential_material_accessed: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    production_ready: bool = False

    @field_validator(
        "capability_id",
        "scenario",
        "broker_decision",
        "broker_evidence_status",
        "broker_evidence_type",
    )
    @classmethod
    def _validate_optional_text(cls, value: Optional[str], info: object) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)

    @field_validator("blocked_reasons", "required_requirements", "missing_requirements", "operator_next_steps")
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: object) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
