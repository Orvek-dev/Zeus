from __future__ import annotations

from typing import Final, Optional

from .models import (
    ObjectiveRiskProfile,
    Resolution,
    RiskClass,
    RiskContext,
    Triage,
    Unknown,
    UnknownResolution,
)
from .rules import (
    hard_question_reason,
    sample_cost_exceeds_cap,
    time_breaches_budget,
)
from .voi import threshold_for, voi_score

# Question ordering: when several unknowns must be asked, surface the ones whose
# wrong-guess damage is highest first, breaking ties by risk-class severity.
_CLASS_PRIORITY: Final[dict[RiskClass, int]] = {
    RiskClass.external: 0,
    RiskClass.cost: 1,
    RiskClass.access: 2,
    RiskClass.data: 3,
    RiskClass.time: 4,
    RiskClass.quality: 5,
}

_DEFAULT_QUESTION: Final = "Which missing detail would change how this runs?"


def assess_objective_risk(
    *,
    triage: Triage,
    unknowns: tuple[Unknown, ...],
    context: Optional[RiskContext] = None,
    override_just_do_it: bool = False,
) -> ObjectiveRiskProfile:
    """Decide question/assume/learn/defer per unknown and derive the question set.

    The number of questions is an OUTPUT of the risk shape, never a fixed input:
    a tidy-my-folder objective yields zero, a bank-transfer objective yields
    several, because more high-stakes risk classes fire.
    """
    ctx = context if context is not None else RiskContext()
    threshold = threshold_for(triage)
    escalate_time = time_breaches_budget(ctx)
    escalate_sample = sample_cost_exceeds_cap(ctx)

    resolutions = tuple(
        _classify(
            unknown=unknown,
            triage=triage,
            threshold=threshold,
            escalate_time=escalate_time,
            escalate_sample=escalate_sample,
            override_just_do_it=override_just_do_it,
        )
        for unknown in unknowns
    )

    questioned = tuple(item for item in resolutions if item.resolution is Resolution.question)
    ordered = sorted(
        questioned,
        key=lambda item: (-item.voi_score, _CLASS_PRIORITY[item.risk_class], item.unknown_id),
    )
    questions = tuple(item.question or _DEFAULT_QUESTION for item in ordered)
    assumptions = tuple(
        _assumption_line(item) for item in resolutions if item.resolution is not Resolution.question
    )
    locked_open = sum(1 for item in questioned if item.override_locked)

    return ObjectiveRiskProfile(
        triage=triage,
        resolutions=resolutions,
        questions=questions,
        assumptions=assumptions,
        blocking_question_count=len(questions),
        proceed_allowed_without_answers=locked_open == 0,
        override_applied=override_just_do_it,
    )


def _classify(
    *,
    unknown: Unknown,
    triage: Triage,
    threshold: float,
    escalate_time: bool,
    escalate_sample: bool,
    override_just_do_it: bool,
) -> UnknownResolution:
    score = voi_score(unknown)
    lock_reason = hard_question_reason(unknown)
    if lock_reason is not None:
        return _resolution(
            unknown=unknown,
            resolution=Resolution.question,
            score=score,
            threshold=threshold,
            override_locked=True,
            reasons=(lock_reason,),
        )

    reasons: list[str] = []
    resolution = _baseline_resolution(unknown=unknown, score=score, threshold=threshold, reasons=reasons)

    # Cross-class escalations (override-able only when a safe default exists).
    if unknown.risk_class is RiskClass.time and escalate_time and resolution is not Resolution.question:
        resolution = Resolution.question
        reasons.append("periodicity_breaches_budget")
    if (
        unknown.risk_class is RiskClass.quality
        and escalate_sample
        and resolution is Resolution.learn_by_sample
    ):
        resolution = Resolution.question
        reasons.append("sample_cost_exceeds_cap")

    # "Just do it": accept assumptions for everything that CAN be assumed. A
    # question with a safe default collapses to an assumption; locked questions
    # were already returned above and never reach here.
    if (
        override_just_do_it
        and resolution is Resolution.question
        and unknown.safe_default is not None
    ):
        resolution = Resolution.assume
        reasons.append("override_just_do_it")

    if not reasons:
        reasons.append("voi_below_threshold" if resolution is not Resolution.question else "voi_above_threshold")

    return _resolution(
        unknown=unknown,
        resolution=resolution,
        score=score,
        threshold=threshold,
        override_locked=False,
        reasons=tuple(reasons),
    )


def _baseline_resolution(
    *,
    unknown: Unknown,
    score: float,
    threshold: float,
    reasons: list[str],
) -> Resolution:
    if unknown.sample_learnable:
        reasons.append("quality_learned_by_sample")
        return Resolution.learn_by_sample
    if score > threshold:
        reasons.append("voi_above_threshold")
        return Resolution.question
    if unknown.deferrable:
        reasons.append("decision_deferred_to_node")
        return Resolution.defer
    if unknown.safe_default is not None:
        reasons.append("safe_default_assumed")
        return Resolution.assume
    # No safe default, low VoI, not deferrable/learnable: still ask, but softly
    # (not override-locked) — we have nothing to fall back on.
    reasons.append("no_safe_default_available")
    return Resolution.question


def _resolution(
    *,
    unknown: Unknown,
    resolution: Resolution,
    score: float,
    threshold: float,
    override_locked: bool,
    reasons: tuple[str, ...],
) -> UnknownResolution:
    question = None
    assumed = None
    if resolution is Resolution.question:
        question = unknown.question_text or unknown.description
    elif unknown.safe_default is not None:
        assumed = unknown.safe_default.value
    return UnknownResolution(
        unknown_id=unknown.unknown_id,
        risk_class=unknown.risk_class,
        resolution=resolution,
        voi_score=score,
        threshold=threshold,
        override_locked=override_locked,
        reasons=reasons,
        question=question,
        assumed_value=assumed,
    )


def _assumption_line(item: UnknownResolution) -> str:
    if item.resolution is Resolution.learn_by_sample:
        return "{0}: learn from a sample before committing".format(item.unknown_id)
    if item.resolution is Resolution.defer:
        return "{0}: decide at the node that needs it".format(item.unknown_id)
    if item.assumed_value is not None:
        return "{0}: assumed {1}".format(item.unknown_id, item.assumed_value)
    return "{0}: assumed default".format(item.unknown_id)
