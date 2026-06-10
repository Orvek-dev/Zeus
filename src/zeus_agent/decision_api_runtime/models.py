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
)

from zeus_agent.trust_loop_runtime import TrustDecision


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class HostKind(str, Enum):
    claude_code = "claude_code"
    hermes = "hermes"
    openclaw = "openclaw"
    console = "console"


class GateSurface(str, Enum):
    hook = "hook"
    llm_proxy = "llm_proxy"
    mcp_gateway = "mcp_gateway"
    egress = "egress"
    console = "console"


class Obligation(str, Enum):
    """Duties the host accepts alongside an allowed decision."""

    require_undo_plan = "require_undo_plan"
    require_evidence = "require_evidence"
    redact_response = "redact_response"
    notify_digest = "notify_digest"
    quiet_hold = "quiet_hold"


class DecisionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    host: HostKind
    surface: GateSurface
    objective_id: Optional[str] = None
    observed_taint: tuple[str, ...] = ()
    parent_principal_id: Optional[str] = None
    state_hash: Optional[str] = None


class DecisionRequest(BaseModel):
    """The common contract every gate sends to the kernel.

    Zeus decides and records; the HOST executes its own tool. Args are
    redacted on ingest before they ever reach the ledger.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    principal_id: str
    session_id: str
    run_id: str
    capability_id: str
    args: dict[str, JsonValue] = Field(default_factory=dict)
    requested_units: int = Field(default=1, ge=0)
    context: DecisionContext

    @field_validator("principal_id", "session_id", "run_id", "capability_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    decision: TrustDecision
    reason: str
    receipt_id: str
    obligations: tuple[Obligation, ...] = ()
    parked_action_id: Optional[str] = None
    envelope_ref: Optional[str] = None
    ttl_ms: int = 0

    @field_validator("reason", "receipt_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)
