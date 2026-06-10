from __future__ import annotations

from zeus_agent.promotion_runtime import (
    PromotionCandidate,
    PromotionKind,
    review_promotion,
)
from zeus_agent.skill_eval_loop_runtime import SkillRunResult, evaluate_skill


def _candidate(**overrides: object) -> PromotionCandidate:
    base: dict[str, object] = {
        "candidate_id": "skill.summarize",
        "kind": PromotionKind.skill,
        "title": "summarize",
        "evidence_ids": ("ev.1", "ev.2"),
        "score": 0.95,
        "reversible": True,
        "hard_risk": False,
    }
    base.update(overrides)
    return PromotionCandidate(**base)  # type: ignore[arg-type]


# --- Promotion contract -----------------------------------------------------


def test_no_evidence_blocks_promotion() -> None:
    decision = review_promotion(_candidate(evidence_ids=()), golden_set_passed=True)
    assert decision.promoted is False
    assert "no_evidence" in decision.reasons


def test_failed_golden_set_blocks_goodhart() -> None:
    # High score but golden set failed → blocked (the Goodhart guard).
    decision = review_promotion(_candidate(score=0.99), golden_set_passed=False)
    assert decision.promoted is False
    assert "golden_set_failed" in decision.reasons


def test_low_score_blocks() -> None:
    decision = review_promotion(_candidate(score=0.5), golden_set_passed=True)
    assert decision.promoted is False
    assert "score_below_threshold" in decision.reasons


def test_low_risk_reversible_auto_promotes_with_rollback_token() -> None:
    decision = review_promotion(_candidate(), golden_set_passed=True)
    assert decision.promoted is True
    assert decision.status == "promoted"
    assert decision.rollback_token is not None


def test_hard_risk_never_auto_promotes() -> None:
    blocked = review_promotion(_candidate(hard_risk=True), golden_set_passed=True)
    assert blocked.promoted is False
    assert blocked.status == "needs_human_review"
    # ...but a human can promote it.
    approved = review_promotion(_candidate(hard_risk=True), golden_set_passed=True, human_reviewed=True)
    assert approved.promoted is True


def test_irreversible_requires_human_review() -> None:
    decision = review_promotion(_candidate(reversible=False), golden_set_passed=True)
    assert decision.status == "needs_human_review"
    assert "irreversible_requires_human_review" in decision.reasons


# --- Skill eval closed loop -------------------------------------------------


def _runner(pass_set: set):
    def run(skill_id: str, case: str) -> SkillRunResult:
        return SkillRunResult(case_id=case, passed=case in pass_set, cost_units=1)
    return run


def test_skill_passing_golden_set_promotes() -> None:
    cases = ("c1", "c2", "c3", "c4", "c5")
    report = evaluate_skill(
        skill_id="skill.summarize", candidate_title="summarize", golden_cases=cases,
        runner=_runner({"c1", "c2", "c3", "c4", "c5"}), evidence_ids=("ev.1",),
    )
    assert report.pass_rate == 1.0
    assert report.golden_set_passed is True
    assert report.decision.promoted is True


def test_skill_failing_golden_set_is_blocked() -> None:
    cases = ("c1", "c2", "c3", "c4", "c5")
    report = evaluate_skill(
        skill_id="skill.summarize", candidate_title="summarize", golden_cases=cases,
        runner=_runner({"c1", "c2"}), evidence_ids=("ev.1",),  # 2/5 = 0.4
    )
    assert report.pass_rate == 0.4
    assert report.golden_set_passed is False
    assert report.decision.promoted is False
    assert "golden_set_failed" in report.decision.reasons


def test_skill_eval_measures_cost() -> None:
    report = evaluate_skill(
        skill_id="skill.x", candidate_title="x", golden_cases=("a", "b"),
        runner=_runner({"a", "b"}), evidence_ids=("ev.1",),
    )
    assert report.total_cost_units == 2
    assert report.cases_run == 2
