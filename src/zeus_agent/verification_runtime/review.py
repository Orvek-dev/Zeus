from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.security.credentials import redact_secret_spans

ReviewDecision = Literal["approved", "blocked"]
ReviewVerdict = Literal["approved", "changes_requested", "blocked"]
_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ReviewBindingRequest(BaseModel):
    model_config = _MODEL_CONFIG

    change_set_id: str
    producer_id: str
    reviewer_id: str
    verdict: ReviewVerdict
    reviewed_paths: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    findings: tuple[str, ...] = ()

    @field_validator("change_set_id", "producer_id", "reviewer_id")
    @classmethod
    def _redact_text(cls, value: str) -> str:
        redacted = redact_secret_spans(value)
        if not redacted:
            raise ValueError("review_field_empty")
        return redacted

    @field_validator("reviewed_paths", "evidence_ids", "findings")
    @classmethod
    def _redact_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(redact_secret_spans(value) for value in values if value.strip())


class ReviewBindingResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ReviewDecision
    reason: str
    blocked_reasons: tuple[str, ...]
    change_set_id: str
    producer_id: str
    reviewer_id: str
    reviewed_paths: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    findings: tuple[str, ...]
    review_required: bool
    no_secret_echo: bool = True
    handler_executed: bool = False
    network_opened: bool = False


def bind_review(request: ReviewBindingRequest) -> ReviewBindingResult:
    blocked_reasons = _blocked_reasons(request)
    decision: ReviewDecision = "blocked" if blocked_reasons else "approved"
    return ReviewBindingResult(
        decision=decision,
        reason="independent_review_bound" if decision == "approved" else "review_binding_blocked",
        blocked_reasons=blocked_reasons,
        change_set_id=request.change_set_id,
        producer_id=request.producer_id,
        reviewer_id=request.reviewer_id,
        reviewed_paths=request.reviewed_paths,
        evidence_ids=request.evidence_ids,
        findings=request.findings,
        review_required=decision == "blocked",
        no_secret_echo=_no_secret_echo(request),
    )


def _blocked_reasons(request: ReviewBindingRequest) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.producer_id == request.reviewer_id:
        reasons.append("producer_self_review")
    if request.verdict != "approved":
        reasons.append("review_not_approved")
    if not request.reviewed_paths:
        reasons.append("missing_reviewed_paths")
    if not request.evidence_ids:
        reasons.append("missing_evidence_ids")
    return tuple(reasons)


def _no_secret_echo(request: ReviewBindingRequest) -> bool:
    serialized = request.model_dump_json().lower()
    raw_markers = ("sk-", "ghp_", "github_pat_", "glpat-", "xoxb-", "token=", "password=", "bearer ")
    return not any(marker in serialized for marker in raw_markers)


__all__ = [
    "ReviewBindingRequest",
    "ReviewBindingResult",
    "bind_review",
]
