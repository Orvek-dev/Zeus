from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

WorkflowPattern = Literal[
    "blocked",
    "classify_and_act",
    "fan_out_and_synthesize",
    "adversarial_verification",
    "generate_and_filter",
    "tournament",
    "loop_until_done",
    "lean_ulw",
]
WorkflowDecision = Literal["compiled", "blocked"]
WorkflowRiskLevel = Literal["low", "normal", "high"]
WhyNotDecision = Literal["continue", "fan_out", "adversarial_review", "lean_down", "blocked"]
MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class WorkflowCritiqueCheckpoint(BaseModel):
    model_config = MODEL_CONFIG

    objective_id: str
    starting_pattern: WorkflowPattern
    critique_question: str
    adaptation_decision: WorkflowPattern
    evidence_target: str
    rejected_alternatives: tuple[WorkflowPattern, ...]
    reusable_lesson_candidate: str
    memory_write_performed: bool = False
    authority_widened: bool = False
    network_opened: bool = False
    live_production_claimed: bool = False


def build_critique_checkpoint(
    *,
    objective_id: str,
    pattern: WorkflowPattern,
    risk_level: WorkflowRiskLevel,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    evidence_target: str,
) -> WorkflowCritiqueCheckpoint:
    return WorkflowCritiqueCheckpoint(
        objective_id=objective_id,
        starting_pattern=pattern,
        critique_question=_critique_question(pattern),
        adaptation_decision=pattern,
        evidence_target=evidence_target,
        rejected_alternatives=_rejected_alternatives(pattern),
        reusable_lesson_candidate=_reusable_lesson_candidate(
            pattern=pattern,
            risk_level=risk_level,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
        ),
        memory_write_performed=False,
        authority_widened=False,
        network_opened=False,
        live_production_claimed=False,
    )


def _critique_question(pattern: WorkflowPattern) -> str:
    if pattern == "lean_ulw":
        return "Why not minimize orchestration overhead and keep one controlled lane?"
    if pattern == "fan_out_and_synthesize":
        return "Why not fan out disjoint work before synthesis?"
    if pattern == "adversarial_verification":
        return "Why not add independent adversarial verification before completion?"
    if pattern == "blocked":
        return "Why not stop before unsafe workflow adaptation?"
    return "Why not classify first, then act with the narrowest workflow?"


def _rejected_alternatives(pattern: WorkflowPattern) -> tuple[WorkflowPattern, ...]:
    if pattern == "lean_ulw":
        return ("fan_out_and_synthesize", "adversarial_verification")
    if pattern == "fan_out_and_synthesize":
        return ("lean_ulw", "classify_and_act")
    if pattern == "adversarial_verification":
        return ("lean_ulw", "fan_out_and_synthesize")
    if pattern == "blocked":
        return ()
    return ("fan_out_and_synthesize", "adversarial_verification")


def _reusable_lesson_candidate(
    *,
    pattern: WorkflowPattern,
    risk_level: WorkflowRiskLevel,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
) -> str:
    return "Use {0} for risk={1}, tasks={2}, code={3}, research={4}.".format(
        pattern,
        risk_level,
        task_count,
        requires_code,
        requires_research,
    )
