from __future__ import annotations

from pathlib import Path
from typing import Optional

from zeus_agent.adaptive_zeus_runtime import build_adaptive_zeus_contract
from zeus_agent.goal_intelligence_runtime.factory import build_contract
from zeus_agent.goal_intelligence_runtime.helpers import no_unsafe_side_effects
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceContract
from zeus_agent.goal_intelligence_runtime.scenarios import understand_objective_contract
from zeus_agent.real_memory_operation_runtime import build_real_memory_operation_contract
from zeus_agent.real_self_evolution_runtime import build_real_self_evolution_contract


def status_contract(
    *,
    home: Optional[Path],
    objective: str,
    interview_answers: tuple[str, ...] = (),
    cognitive_provider_output: Optional[str] = None,
) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="status",
        objective=objective,
        task_count=4,
        requires_code=False,
        requires_research=False,
        risk_level="normal",
        interview_answers=interview_answers,
        cognitive_provider_output=cognitive_provider_output,
    )
    if understood.decision == "blocked":
        return understood
    adaptive = build_adaptive_zeus_contract(
        objective=understood.normalized_goal or objective,
        task_count=4,
        requires_code=False,
        requires_research=False,
        risk_level="normal",
        evidence_target="v220.goal-intelligence.status",
    ).to_payload()
    memory = build_real_memory_operation_contract(scenario="status", home=home).to_payload()
    evolution = build_real_self_evolution_contract(scenario="status", home=home, objective=objective).to_payload()
    ready = (
        understood.decision == "report"
        and understood.objective_understood
        and adaptive["decision"] == "report"
        and memory["decision"] == "report"
        and evolution["decision"] == "report"
        and no_unsafe_side_effects(adaptive, memory, evolution)
    )
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="status",
        normalized_objective=understood.normalized_objective,
        objective_id=understood.objective_id,
        goal_contract_id=understood.goal_contract_id,
        normalized_goal=understood.normalized_goal,
        acceptance_criteria=understood.acceptance_criteria,
        intent_frame=understood.intent_frame,
        blocked_reasons=() if ready else ("goal_intelligence_status_unavailable",),
        objective_contract=understood.objective_contract,
        adaptive_contract=adaptive,
        memory_contract=memory,
        self_evolution_contract=evolution,
        user_context_model=understood.user_context_model,
        goal_intelligence_ready=ready,
        objective_understood=understood.objective_understood,
        adaptive_replan_ready=adaptive["decision"] == "report",
        workflow_critic_ready=adaptive["decision"] == "report",
        eval_loop_ready=evolution["decision"] == "report",
        parallel_task_count=int(adaptive["parallel_task_count"]),
        eval_record_count=int(evolution["eval_record_count"]),
        learning_candidate_count=int(evolution["learning_candidate_count"]),
    )


def adaptive_replan_contract(
    *,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
    interview_answers: tuple[str, ...] = (),
    cognitive_provider_output: Optional[str] = None,
) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="adaptive-replan",
        objective=objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        interview_answers=interview_answers,
        cognitive_provider_output=cognitive_provider_output,
    )
    if understood.decision == "blocked":
        return understood
    if not understood.objective_understood:
        return build_contract(
            decision="blocked",
            scenario="adaptive-replan",
            blocked_reasons=("objective_not_understood",),
            normalized_objective=understood.normalized_objective,
            objective_id=understood.objective_id,
            goal_contract_id=understood.goal_contract_id,
            normalized_goal=understood.normalized_goal,
            acceptance_criteria=understood.acceptance_criteria,
            intent_frame=understood.intent_frame,
            objective_contract=understood.objective_contract,
            user_context_model=understood.user_context_model,
            interview_questions=understood.interview_questions,
            interview_required=True,
        )
    adaptive = build_adaptive_zeus_contract(
        objective=understood.normalized_goal or objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        evidence_target="v220.goal-intelligence.adaptive-replan",
    ).to_payload()
    ready = adaptive["decision"] == "report" and no_unsafe_side_effects(adaptive)
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="adaptive-replan",
        blocked_reasons=() if ready else tuple(str(reason) for reason in adaptive["blocked_reasons"]),
        normalized_objective=understood.normalized_objective,
        objective_id=understood.objective_id,
        goal_contract_id=understood.goal_contract_id,
        normalized_goal=understood.normalized_goal,
        acceptance_criteria=understood.acceptance_criteria,
        intent_frame=understood.intent_frame,
        objective_contract=understood.objective_contract,
        adaptive_contract=adaptive,
        user_context_model=understood.user_context_model,
        interview_questions=understood.interview_questions,
        goal_intelligence_ready=ready,
        objective_understood=understood.objective_understood,
        interview_required=understood.interview_required,
        adaptive_replan_ready=ready,
        workflow_critic_ready=ready,
        parallel_task_count=int(adaptive["parallel_task_count"]),
    )


def ontology_context_contract(
    *,
    home: Optional[Path],
    objective: str,
    interview_answers: tuple[str, ...] = (),
    cognitive_provider_output: Optional[str] = None,
) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="ontology-context",
        objective=objective,
        task_count=2,
        requires_code=False,
        requires_research=False,
        risk_level="normal",
        interview_answers=interview_answers,
        cognitive_provider_output=cognitive_provider_output,
    )
    if understood.decision == "blocked":
        return understood
    if not understood.objective_understood:
        return build_contract(
            decision="blocked",
            scenario="ontology-context",
            blocked_reasons=("objective_not_understood",),
            normalized_objective=understood.normalized_objective,
            objective_id=understood.objective_id,
            goal_contract_id=understood.goal_contract_id,
            normalized_goal=understood.normalized_goal,
            acceptance_criteria=understood.acceptance_criteria,
            intent_frame=understood.intent_frame,
            objective_contract=understood.objective_contract,
            user_context_model=understood.user_context_model,
            interview_questions=understood.interview_questions,
            interview_required=True,
        )
    memory = build_real_memory_operation_contract(
        scenario="ontology-wiki-smoke",
        home=home,
        subject="ZeusGoalIntelligence",
    ).to_payload()
    ready = (
        memory["decision"] == "report"
        and memory["ontology_wiki_ready"] is True
        and memory["memory_auto_promotion"] is False
        and memory["ontology_auto_promotion"] is False
        and no_unsafe_side_effects(memory)
    )
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="ontology-context",
        blocked_reasons=() if ready else tuple(str(reason) for reason in memory["blocked_reasons"]),
        normalized_objective=understood.normalized_objective,
        objective_id=understood.objective_id,
        goal_contract_id=understood.goal_contract_id,
        normalized_goal=understood.normalized_goal,
        acceptance_criteria=understood.acceptance_criteria,
        intent_frame=understood.intent_frame,
        objective_contract=understood.objective_contract,
        memory_contract=memory,
        user_context_model=understood.user_context_model,
        goal_intelligence_ready=ready,
        objective_understood=understood.objective_understood,
        context_ontology_ready=ready,
        ontology_candidate_count=int(memory["ontology_candidate_count"]),
        ontology_review_queue_count=int(memory["ontology_review_queue_count"]),
        memory_write_executed=bool(memory["memory_write_executed"]),
    )
