from __future__ import annotations

from enum import Enum
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


_MIN_SCORE: Final = 0.8


class PromotionKind(str, Enum):
    capability = "capability"
    skill = "skill"
    memory = "memory"
    ontology = "ontology"
    rule = "rule"


class PromotionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    candidate_id: str
    kind: PromotionKind
    title: str
    evidence_ids: tuple[str, ...] = ()
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    reversible: bool = True
    hard_risk: bool = False

    @field_validator("candidate_id", "title")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class PromotionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    candidate_id: str
    status: str  # promoted | needs_human_review | blocked
    promoted: bool
    reasons: tuple[str, ...]
    rollback_token: Optional[str] = None


def review_promotion(
    candidate: PromotionCandidate,
    *,
    human_reviewed: bool = False,
    golden_set_passed: bool = False,
) -> PromotionDecision:
    """Decide whether a candidate may promote.

    Fail-closed: no evidence, a failed golden set (Goodhart guard), or a low
    score blocks. Hard-risk candidates always require human review. Otherwise,
    low-risk reversible candidates auto-promote; the rest need human review.
    """
    blocked: list[str] = []
    if not candidate.evidence_ids:
        blocked.append("no_evidence")
    if not golden_set_passed:
        blocked.append("golden_set_failed")
    if candidate.score < _MIN_SCORE:
        blocked.append("score_below_threshold")
    if blocked:
        return PromotionDecision(
            candidate_id=candidate.candidate_id, status="blocked", promoted=False,
            reasons=tuple(blocked),
        )

    needs_review = candidate.hard_risk or not candidate.reversible
    if needs_review and not human_reviewed:
        reason = "hard_risk_requires_human_review" if candidate.hard_risk else "irreversible_requires_human_review"
        return PromotionDecision(
            candidate_id=candidate.candidate_id, status="needs_human_review", promoted=False,
            reasons=(reason,),
        )

    reason = "human_reviewed" if human_reviewed else "earned_low_risk_reversible"
    return PromotionDecision(
        candidate_id=candidate.candidate_id, status="promoted", promoted=True,
        reasons=(reason,),
        rollback_token="rollback.{0}".format(candidate.candidate_id.replace(".", "_")),
    )
