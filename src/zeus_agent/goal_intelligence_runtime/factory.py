from __future__ import annotations

from typing import Optional

from pydantic import JsonValue

from zeus_agent.goal_intelligence_runtime.helpers import any_flag
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceContract
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceDecision
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceScenario


def build_contract(
    *,
    decision: GoalIntelligenceDecision,
    scenario: GoalIntelligenceScenario,
    blocked_reasons: tuple[str, ...] = (),
    normalized_objective: str = "",
    objective_id: Optional[str] = None,
    interview_questions: tuple[str, ...] = (),
    user_context_model: Optional[dict[str, JsonValue]] = None,
    goal_intelligence_ready: bool = False,
    objective_understood: bool = False,
    interview_required: bool = False,
    adaptive_replan_ready: bool = False,
    deep_interview_ready: bool = False,
    user_context_update_candidate: bool = False,
    context_ontology_ready: bool = False,
    workflow_critic_ready: bool = False,
    eval_loop_ready: bool = False,
    raw_secret_marker_detected: bool = False,
    objective_contract: Optional[dict[str, JsonValue]] = None,
    adaptive_contract: Optional[dict[str, JsonValue]] = None,
    memory_contract: Optional[dict[str, JsonValue]] = None,
    self_evolution_contract: Optional[dict[str, JsonValue]] = None,
    parallel_task_count: int = 0,
    ontology_candidate_count: int = 0,
    ontology_review_queue_count: int = 0,
    eval_record_count: int = 0,
    learning_candidate_count: int = 0,
    memory_write_executed: bool = False,
) -> GoalIntelligenceContract:
    contracts = tuple(
        value for value in (objective_contract, adaptive_contract, memory_contract, self_evolution_contract) if value
    )
    result = GoalIntelligenceContract(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        normalized_objective=normalized_objective,
        objective_id=objective_id,
        interview_questions=interview_questions,
        interview_question_count=len(interview_questions),
        user_context_model=user_context_model,
        goal_intelligence_ready=goal_intelligence_ready,
        objective_understood=objective_understood,
        interview_required=interview_required,
        deep_interview_ready=deep_interview_ready,
        user_context_update_candidate=user_context_update_candidate,
        context_ontology_ready=context_ontology_ready,
        adaptive_replan_ready=adaptive_replan_ready,
        workflow_critic_ready=workflow_critic_ready,
        eval_loop_ready=eval_loop_ready,
        objective_contract=objective_contract,
        adaptive_contract=adaptive_contract,
        memory_contract=memory_contract,
        self_evolution_contract=self_evolution_contract,
        parallel_task_count=parallel_task_count,
        ontology_candidate_count=ontology_candidate_count,
        ontology_review_queue_count=ontology_review_queue_count,
        eval_record_count=eval_record_count,
        learning_candidate_count=learning_candidate_count,
        memory_write_executed=memory_write_executed,
        raw_secret_marker_detected=raw_secret_marker_detected,
        workflow_self_modification=any_flag(contracts, "workflow_self_modification"),
        workflow_memory_auto_write=any_flag(contracts, "workflow_memory_auto_write"),
        workflow_pattern_promoted=any_flag(contracts, "workflow_pattern_promoted"),
        memory_auto_promotion=any_flag(contracts, "memory_auto_promotion"),
        ontology_auto_promotion=any_flag(contracts, "ontology_auto_promotion"),
        wiki_page_update_written=any_flag(contracts, "wiki_page_update_written"),
        active_skill_written=any_flag(contracts, "active_skill_written"),
        active_rule_written=any_flag(contracts, "active_rule_written"),
        authority_widened=any_flag(contracts, "authority_widened"),
        credential_material_accessed=any_flag(contracts, "credential_material_accessed"),
        network_opened=any_flag(contracts, "network_opened"),
        external_delivery_opened=any_flag(contracts, "external_delivery_opened"),
        handler_executed=any_flag(contracts, "handler_executed"),
        live_production_claimed=any_flag(contracts, "live_production_claimed"),
    )
    return result.with_secret_scan()
