from __future__ import annotations

from pathlib import Path
from typing import Optional

from zeus_agent.goal_intelligence_runtime.factory import build_contract
from zeus_agent.goal_intelligence_runtime.helpers import has_secret_marker
from zeus_agent.goal_intelligence_runtime.helpers import parse_scenario
from zeus_agent.goal_intelligence_runtime.models import GoalIntelligenceContract
from zeus_agent.goal_intelligence_runtime.composed import adaptive_replan_contract
from zeus_agent.goal_intelligence_runtime.composed import ontology_context_contract
from zeus_agent.goal_intelligence_runtime.composed import status_contract
from zeus_agent.goal_intelligence_runtime.scenarios import deep_interview_contract
from zeus_agent.goal_intelligence_runtime.scenarios import understand_objective_contract

_DEFAULT_OBJECTIVE = "Help Zeus understand the user goal and choose a safe adaptive execution workflow."


def build_goal_intelligence_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    objective: str = _DEFAULT_OBJECTIVE,
    task_count: int = 4,
    requires_code: bool = False,
    requires_research: bool = False,
    risk_level: str = "normal",
    interview_answers: tuple[str, ...] = (),
    proceed_override: bool = False,
    cognitive_provider_output: Optional[str] = None,
) -> GoalIntelligenceContract:
    parsed = parse_scenario(scenario.strip())
    if parsed is None:
        return build_contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_goal_intelligence_scenario",),
        )
    if has_secret_marker(objective):
        return build_contract(
            decision="blocked",
            scenario=parsed,
            normalized_objective="[redacted-secret]",
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        )
    if has_secret_marker(*interview_answers, cognitive_provider_output):
        return build_contract(
            decision="blocked",
            scenario=parsed,
            normalized_objective="[redacted-secret]",
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        )
    if parsed == "status":
        return status_contract(
            home=home,
            objective=objective,
            interview_answers=interview_answers,
            cognitive_provider_output=cognitive_provider_output,
        )
    if parsed == "understand-objective":
        return understand_objective_contract(
            scenario=parsed,
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            interview_answers=interview_answers,
            cognitive_provider_output=cognitive_provider_output,
        )
    if parsed == "deep-interview":
        return deep_interview_contract(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            interview_answers=interview_answers,
            proceed_override=proceed_override,
            cognitive_provider_output=cognitive_provider_output,
        )
    if parsed == "adaptive-replan":
        return adaptive_replan_contract(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            interview_answers=interview_answers,
            cognitive_provider_output=cognitive_provider_output,
        )
    return ontology_context_contract(
        home=home,
        objective=objective,
        interview_answers=interview_answers,
        cognitive_provider_output=cognitive_provider_output,
    )
