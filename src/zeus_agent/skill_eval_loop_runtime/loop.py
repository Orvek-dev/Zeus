from __future__ import annotations

from typing import Callable, Final

from pydantic import BaseModel, ConfigDict, Field

from zeus_agent.promotion_runtime import (
    PromotionCandidate,
    PromotionDecision,
    PromotionKind,
    review_promotion,
)

_GOLDEN_PASS_THRESHOLD: Final = 0.8


class SkillRunResult(BaseModel):
    """One golden-case run: did the skill pass, and what did it cost. In
    production this comes from a sandbox run; in tests, a deterministic stub."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    case_id: str
    passed: bool
    cost_units: int = Field(default=0, ge=0)


SkillRunner = Callable[[str, str], SkillRunResult]


class SkillEvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    skill_id: str
    cases_run: int = Field(ge=0)
    cases_passed: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    total_cost_units: int = Field(ge=0)
    golden_set_passed: bool
    decision: PromotionDecision


def evaluate_skill(
    *,
    skill_id: str,
    candidate_title: str,
    golden_cases: tuple[str, ...],
    runner: SkillRunner,
    evidence_ids: tuple[str, ...],
    hard_risk: bool = False,
    reversible: bool = True,
    human_reviewed: bool = False,
) -> SkillEvalReport:
    """Run the skill against the golden set, measure, and gate promotion on it."""
    if not golden_cases:
        raise ValueError("golden_cases_required")
    results = [runner(skill_id, case) for case in golden_cases]
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    pass_rate = passed / total
    total_cost = sum(r.cost_units for r in results)
    golden_passed = pass_rate >= _GOLDEN_PASS_THRESHOLD

    candidate = PromotionCandidate(
        candidate_id=skill_id,
        kind=PromotionKind.skill,
        title=candidate_title,
        evidence_ids=evidence_ids,
        score=round(pass_rate, 4),
        reversible=reversible,
        hard_risk=hard_risk,
    )
    decision = review_promotion(
        candidate, human_reviewed=human_reviewed, golden_set_passed=golden_passed
    )
    return SkillEvalReport(
        skill_id=skill_id,
        cases_run=total,
        cases_passed=passed,
        pass_rate=round(pass_rate, 4),
        total_cost_units=total_cost,
        golden_set_passed=golden_passed,
        decision=decision,
    )
