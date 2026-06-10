from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class ExecutionClaim(BaseModel):
    """A surface's claim about one execution, normalized for the integrity gate."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    surface: str
    handler_executed: bool
    broker_evidence_bound: bool
    evidence_record_id: Optional[str] = None

    @field_validator("surface")
    @classmethod
    def validate_surface(cls, value: str) -> str:
        return require_text(value, "surface")


class IntegrityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    surface: str
    reason: str


class IntegrityVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    ok: bool
    checked: int = Field(ge=0)
    findings: tuple[IntegrityFinding, ...] = ()


class ExecutionIntegrityError(RuntimeError):
    """A handler ran without leaving broker evidence — a chokepoint breach.

    Raised by surfaces that enforce the gate inline (fail-closed): this is a
    'should never happen' invariant, so it is loud rather than swallowed.
    """


def assert_claim(claim: ExecutionClaim) -> None:
    reason = claim_violation(claim)
    if reason is not None:
        raise ExecutionIntegrityError("{0}:{1}".format(claim.surface, reason))


def claim_violation(claim: ExecutionClaim) -> Optional[str]:
    """Return a violation reason if this claim breaches the chokepoint invariant.

    A handler that ran must have bound broker evidence AND left a record id.
    Anything that did not run a handler is trivially fine.
    """
    if not claim.handler_executed:
        return None
    if not claim.broker_evidence_bound:
        return "handler_executed_without_broker_evidence"
    if claim.evidence_record_id is None or claim.evidence_record_id.strip() == "":
        return "handler_executed_without_evidence_record"
    return None


def gate_executions(claims: tuple[ExecutionClaim, ...]) -> IntegrityVerdict:
    """Fail-closed over a set of claims: the gate is ok only if none violate."""
    findings: list[IntegrityFinding] = []
    for claim in claims:
        reason = claim_violation(claim)
        if reason is not None:
            findings.append(IntegrityFinding(surface=claim.surface, reason=reason))
    return IntegrityVerdict(ok=len(findings) == 0, checked=len(claims), findings=tuple(findings))


def claim_from_decision_receipt(receipt: object, *, surface: str = "trust_loop") -> ExecutionClaim:
    """Adapter for ``trust_loop_runtime.DecisionReceipt`` (duck-typed)."""
    return ExecutionClaim(
        surface=surface,
        handler_executed=bool(getattr(receipt, "handler_executed", False)),
        broker_evidence_bound=bool(getattr(receipt, "broker_evidence_bound", False)),
        evidence_record_id=_optional_str(getattr(receipt, "evidence_record_id", None)),
    )


def claim_from_provider_receipt(receipt: object, *, surface: str = "provider") -> ExecutionClaim:
    """Adapter for ``provider_capability_runtime.ProviderReceipt`` (duck-typed)."""
    return ExecutionClaim(
        surface=surface,
        handler_executed=bool(getattr(receipt, "handler_executed", False)),
        broker_evidence_bound=bool(getattr(receipt, "broker_evidence_bound", False)),
        evidence_record_id=_optional_str(getattr(receipt, "evidence_record_id", None)),
    )


def _optional_str(value: object) -> Optional[str]:
    if isinstance(value, str) and value.strip() != "":
        return value
    return None
