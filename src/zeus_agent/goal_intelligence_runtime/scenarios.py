from __future__ import annotations

from typing import Optional

from pydantic import ValidationError

from zeus_agent.goal_intelligence_runtime.factory import build_contract
from zeus_agent.goal_intelligence_runtime.helpers import user_context_model
from zeus_agent.goal_intelligence_runtime.intent import build_intent_frame
from zeus_agent.goal_intelligence_runtime.intent import interview_questions_for
from zeus_agent.goal_intelligence_runtime.intent import residual_assumptions_for
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceContract
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceScenario
from zeus_agent.goal_intelligence_runtime.policy import unsafe_policy_reasons
from zeus_agent.objective_runtime import ObjectiveCompiler


def understand_objective_contract(
    *,
    scenario: GoalIntelligenceScenario,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
    interview_answers: tuple[str, ...] = (),
    cognitive_provider_output: Optional[str] = None,
) -> GoalIntelligenceContract:
    try:
        compiled_objective = ObjectiveCompiler().compile(objective)
        objective_contract = compiled_objective.model_dump(mode="json")
    except ValidationError:
        return build_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("malformed_objective",),
        )
    answer_policy_reasons = (
        unsafe_policy_reasons(" ".join(interview_answers)) if interview_answers else ()
    )
    if answer_policy_reasons:
        return build_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("interview_answer_unsafe", *answer_policy_reasons),
            normalized_objective=compiled_objective.normalized_objective,
            objective_id=compiled_objective.objective_id,
            objective_contract=objective_contract,
        )
    intent_result = build_intent_frame(
        objective=compiled_objective.normalized_objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        interview_answers=interview_answers,
        cognitive_provider_output=cognitive_provider_output,
    )
    if intent_result.blocked_reasons:
        return build_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=intent_result.blocked_reasons,
            normalized_objective=compiled_objective.normalized_objective,
            objective_id=compiled_objective.objective_id,
            intent_frame=intent_result.frame.model_dump(mode="json"),
            cognitive_provider_used=intent_result.cognitive_provider_used,
        )
    blocked = bool(objective_contract["blocked"])
    frame = intent_result.frame
    questions = interview_questions_for(frame)
    context = user_context_model(
        objective=str(objective_contract["normalized_objective"]),
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
    )
    understood = (not blocked) and frame.understood
    return build_contract(
        decision="blocked" if blocked else "report",
        scenario=scenario,
        blocked_reasons=tuple(str(reason) for reason in objective_contract["block_reasons"]),
        normalized_objective=compiled_objective.normalized_objective,
        objective_id=compiled_objective.objective_id,
        goal_contract_id=compiled_objective.objective_id,
        normalized_goal=frame.desired_outcome,
        acceptance_criteria=frame.acceptance_criteria,
        intent_frame=frame.model_dump(mode="json"),
        objective_contract=objective_contract,
        interview_questions=questions,
        interview_answers=interview_answers,
        interview_round_count=1 + len(interview_answers),
        cognitive_provider_used=intent_result.cognitive_provider_used,
        user_context_model=context,
        goal_intelligence_ready=understood,
        objective_understood=understood,
        interview_required=not understood,
    )


def deep_interview_contract(
    *,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
    interview_answers: tuple[str, ...] = (),
    proceed_override: bool = False,
    cognitive_provider_output: Optional[str] = None,
) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="deep-interview",
        objective=objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        interview_answers=interview_answers,
        cognitive_provider_output=cognitive_provider_output,
    )
    residual_assumptions = ()
    residual_recorded = False
    if proceed_override and understood.intent_frame is not None:
        frame = build_intent_frame(
            objective=understood.normalized_objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            interview_answers=interview_answers,
        ).frame
        residual_assumptions = residual_assumptions_for(frame)
        residual_recorded = bool(residual_assumptions)
    return understood.model_copy(
        update={
            "deep_interview_ready": understood.decision == "report" and (
                understood.objective_understood or proceed_override
            ),
            "user_context_update_candidate": understood.decision == "report",
            "proceed_override_used": proceed_override,
            "residual_assumptions_recorded": residual_recorded,
            "intent_frame": _with_residual_assumptions(
                understood.intent_frame,
                residual_assumptions,
            ),
            "workflow_memory_auto_write": False,
            "memory_write_executed": False,
        }
    ).with_secret_scan()


def _with_residual_assumptions(
    intent_frame: Optional[dict[str, object]],
    assumptions: tuple[str, ...],
) -> Optional[dict[str, object]]:
    if intent_frame is None or not assumptions:
        return intent_frame
    updated = dict(intent_frame)
    existing = tuple(str(item) for item in updated.get("assumptions", ()))
    updated["assumptions"] = [*existing, *assumptions]
    return updated
