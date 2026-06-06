from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from zeus_agent.adaptive_zeus_runtime import build_adaptive_zeus_contract
from zeus_agent.goal_intelligence_runtime.factory import build_contract
from zeus_agent.goal_intelligence_runtime.helpers import interview_questions
from zeus_agent.goal_intelligence_runtime.helpers import no_unsafe_side_effects
from zeus_agent.goal_intelligence_runtime.helpers import user_context_model
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceContract
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceScenario
from zeus_agent.objective_runtime import ObjectiveCompiler
from zeus_agent.real_memory_operation_runtime import build_real_memory_operation_contract
from zeus_agent.real_self_evolution_runtime import build_real_self_evolution_contract


def status_contract(*, home: Optional[Path], objective: str) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="status",
        objective=objective,
        task_count=4,
        requires_code=False,
        requires_research=False,
        risk_level="normal",
    )
    adaptive = build_adaptive_zeus_contract(
        objective=objective,
        task_count=4,
        requires_code=False,
        requires_research=False,
        risk_level="normal",
        evidence_target="v200.goal-intelligence.status",
    ).to_payload()
    memory = build_real_memory_operation_contract(scenario="status", home=home).to_payload()
    evolution = build_real_self_evolution_contract(scenario="status", home=home, objective=objective).to_payload()
    ready = (
        understood.decision == "report"
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
        blocked_reasons=() if ready else ("goal_intelligence_status_unavailable",),
        objective_contract=understood.objective_contract,
        adaptive_contract=adaptive,
        memory_contract=memory,
        self_evolution_contract=evolution,
        user_context_model=understood.user_context_model,
        goal_intelligence_ready=ready,
        objective_understood=ready,
        adaptive_replan_ready=adaptive["decision"] == "report",
        workflow_critic_ready=adaptive["decision"] == "report",
        eval_loop_ready=evolution["decision"] == "report",
        parallel_task_count=int(adaptive["parallel_task_count"]),
        eval_record_count=int(evolution["eval_record_count"]),
        learning_candidate_count=int(evolution["learning_candidate_count"]),
    )


def understand_objective_contract(
    *,
    scenario: GoalIntelligenceScenario,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
) -> GoalIntelligenceContract:
    try:
        objective_contract = ObjectiveCompiler().compile(objective).model_dump(mode="json")
    except ValidationError:
        return build_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("malformed_objective",),
        )
    blocked = bool(objective_contract["blocked"])
    questions = interview_questions(
        objective=str(objective_contract["normalized_objective"]),
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
    )
    context = user_context_model(
        objective=str(objective_contract["normalized_objective"]),
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
    )
    return build_contract(
        decision="blocked" if blocked else "report",
        scenario=scenario,
        blocked_reasons=tuple(str(reason) for reason in objective_contract["block_reasons"]),
        normalized_objective=str(objective_contract["normalized_objective"]),
        objective_id=str(objective_contract["objective_id"]),
        objective_contract=objective_contract,
        interview_questions=questions,
        user_context_model=context,
        goal_intelligence_ready=not blocked,
        objective_understood=not blocked,
        interview_required=len(questions) >= 3,
    )


def deep_interview_contract(
    *,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="deep-interview",
        objective=objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
    )
    return understood.model_copy(
        update={
            "deep_interview_ready": understood.decision == "report",
            "user_context_update_candidate": understood.decision == "report",
            "workflow_memory_auto_write": False,
            "memory_write_executed": False,
        }
    ).with_secret_scan()


def adaptive_replan_contract(
    *,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="adaptive-replan",
        objective=objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
    )
    if understood.decision == "blocked":
        return understood
    adaptive = build_adaptive_zeus_contract(
        objective=objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        evidence_target="v200.goal-intelligence.adaptive-replan",
    ).to_payload()
    ready = adaptive["decision"] == "report" and no_unsafe_side_effects(adaptive)
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="adaptive-replan",
        blocked_reasons=() if ready else tuple(str(reason) for reason in adaptive["blocked_reasons"]),
        normalized_objective=understood.normalized_objective,
        objective_id=understood.objective_id,
        objective_contract=understood.objective_contract,
        adaptive_contract=adaptive,
        user_context_model=understood.user_context_model,
        interview_questions=understood.interview_questions,
        goal_intelligence_ready=ready,
        objective_understood=True,
        interview_required=understood.interview_required,
        adaptive_replan_ready=ready,
        workflow_critic_ready=ready,
        parallel_task_count=int(adaptive["parallel_task_count"]),
    )


def ontology_context_contract(*, home: Optional[Path], objective: str) -> GoalIntelligenceContract:
    understood = understand_objective_contract(
        scenario="ontology-context",
        objective=objective,
        task_count=2,
        requires_code=False,
        requires_research=False,
        risk_level="normal",
    )
    if understood.decision == "blocked":
        return understood
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
        objective_contract=understood.objective_contract,
        memory_contract=memory,
        user_context_model=understood.user_context_model,
        goal_intelligence_ready=ready,
        objective_understood=True,
        context_ontology_ready=ready,
        ontology_candidate_count=int(memory["ontology_candidate_count"]),
        ontology_review_queue_count=int(memory["ontology_review_queue_count"]),
        memory_write_executed=bool(memory["memory_write_executed"]),
    )
