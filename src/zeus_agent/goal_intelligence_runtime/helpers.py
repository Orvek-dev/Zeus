from __future__ import annotations

from typing import Optional

from pydantic import JsonValue

from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceScenario
from zeus_agent.security.credentials import contains_secret_material


def parse_scenario(value: str) -> Optional[GoalIntelligenceScenario]:
    if value == "status":
        return "status"
    if value == "understand-objective":
        return "understand-objective"
    if value == "deep-interview":
        return "deep-interview"
    if value == "adaptive-replan":
        return "adaptive-replan"
    if value == "ontology-context":
        return "ontology-context"
    return None


def has_secret_marker(*values: Optional[str]) -> bool:
    joined = " ".join(value for value in values if value is not None)
    return contains_secret_material(joined)


def interview_questions(
    *,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
) -> tuple[str, ...]:
    questions = [
        "What exact outcome should Zeus optimize for first?",
        "What evidence would prove the work is complete?",
        "Which actions require human approval before execution?",
    ]
    if task_count >= 4 or requires_code:
        questions.append("Which implementation scopes can be split without write conflicts?")
    if requires_research:
        questions.append("Which sources should Zeus verify before choosing the workflow?")
    if risk_level == "high":
        questions.append("What rollback path should exist before Zeus starts?")
    if len(objective.split()) < 8:
        questions.append("What domain constraints are missing from the objective?")
    return tuple(dict.fromkeys(questions))


def user_context_model(
    *,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
) -> dict[str, JsonValue]:
    workflow_shape = "single_lane"
    if task_count >= 4 and requires_code and requires_research:
        workflow_shape = "parallel_research_and_code"
    elif task_count >= 4:
        workflow_shape = "parallel_execution"
    elif requires_research:
        workflow_shape = "research_first"
    return {
        "desired_outcome": objective.strip(),
        "task_count": task_count,
        "requires_code": requires_code,
        "requires_research": requires_research,
        "risk_level": risk_level,
        "workflow_shape": workflow_shape,
        "memory_write_mode": "candidate_only",
        "approval_posture": "human_in_the_loop_for_risky_actions",
    }


def any_flag(contracts: tuple[dict[str, JsonValue], ...], key: str) -> bool:
    return any(bool(contract.get(key, False)) for contract in contracts)


def no_unsafe_side_effects(*contracts: dict[str, JsonValue]) -> bool:
    return not any(
        any_flag(
            contracts,
            key,
        )
        for key in (
            "authority_widened",
            "credential_material_accessed",
            "network_opened",
            "external_delivery_opened",
            "handler_executed",
            "live_production_claimed",
        )
    )
