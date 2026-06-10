from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from zeus_agent.trust_loop_runtime import TrustDecision


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class TaintLabel(str, Enum):
    """Information-flow labels carried by a session.

    ``untrusted`` marks data whose author is not the principal (web pages,
    external MCP output, foreign files, the agent's own ledger view).
    ``private`` marks data that must not leave approved sinks (secrets,
    personal files). ``public`` is the neutral floor.
    """

    untrusted = "untrusted"
    private = "private"
    public = "public"


class TaintStamp(BaseModel):
    """One label with the provenance that introduced it.

    Provenance is kept so an approval card can answer "why is this session
    tainted" with the concrete upstream capability or record id.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    label: TaintLabel
    provenance: str

    @field_validator("provenance")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class TaintAssessment(BaseModel):
    """Deterministic verdict of the lethal-trifecta predicates for one action.

    ``forced_decision`` overrides the trust policy outcome (ASK for rule 1,
    DENY for rule 2); ``risk_escalation`` bumps the action risk one tier
    (rule 3). ``tainted``/``taint_sensitive`` feed the existing
    ``_must_ask_for_taint`` path in the trust policy.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    tainted: bool = False
    taint_sensitive: bool = False
    forced_decision: Optional[TrustDecision] = None
    risk_escalation: int = 0
    reasons: tuple[str, ...] = ()
