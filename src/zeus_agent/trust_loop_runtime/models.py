from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationInfo,
    field_validator,
    model_validator,
)


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class TrustDecision(str, Enum):
    AUTO = "auto"
    NOTIFY = "notify"
    ASK = "ask"
    DENY = "deny"


class ActionRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Reversibility(str, Enum):
    reversible = "reversible"
    compensable = "compensable"
    irreversible = "irreversible"


class TrustPolicyProfile(str, Enum):
    cautious = "cautious"
    balanced = "balanced"


class BudgetEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    max_units: int = Field(ge=0)
    requested_units: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_budget(self) -> BudgetEnvelope:
        if self.requested_units > self.max_units:
            raise ValueError("budget_requested_above_envelope")
        return self


class UndoPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    plan_id: str
    strategy: str
    snapshot_ref: str

    @field_validator("plan_id", "strategy", "snapshot_ref")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class ApprovalEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    envelope_id: str
    capability_id: str
    approval_receipt_id: str
    predicted_effects: tuple[str, ...]
    reversibility: Reversibility
    undo_plan: Optional[UndoPlan] = None
    risk: ActionRisk
    budget: BudgetEnvelope

    @field_validator("envelope_id", "capability_id", "approval_receipt_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @field_validator("predicted_effects")
    @classmethod
    def validate_effects(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("predicted_effects_empty")
        return tuple(require_text(value, "predicted_effects") for value in values)


class TrustLoopAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    action_id: str
    run_id: str
    goal_contract_id: str
    criterion_id: str
    capability_id: str
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    risk: ActionRisk = ActionRisk.low
    reversibility: Reversibility = Reversibility.reversible
    tainted: bool = False
    taint_sensitive: bool = False
    budget: BudgetEnvelope
    evidence_target: str = "mneme.v610.trust_loop"
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    live_network: bool = False

    @field_validator(
        "action_id",
        "run_id",
        "goal_contract_id",
        "criterion_id",
        "capability_id",
        "evidence_target",
    )
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @field_validator("credential_scope", "network_host")
    @classmethod
    def validate_optional_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return require_text(value, info.field_name)


class DecisionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    receipt_id: str
    action_id: str
    run_id: str
    capability_id: str
    decision: TrustDecision
    blocked_reason: Optional[str] = None
    handler_executed: bool = False
    broker_evidence_bound: bool = False
    approval_bound: bool = False
    evidence_record_id: str
    cleanup_receipt_id: Optional[str] = None
    undo_token_id: Optional[str] = None
    result: Optional[dict[str, JsonValue]] = None
    no_secret_echo: bool = True

    @field_validator("receipt_id", "action_id", "run_id", "capability_id", "evidence_record_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @field_validator("blocked_reason", "cleanup_receipt_id", "undo_token_id")
    @classmethod
    def validate_optional_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return require_text(value, info.field_name)


class ChainVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    reason: Optional[str] = None
