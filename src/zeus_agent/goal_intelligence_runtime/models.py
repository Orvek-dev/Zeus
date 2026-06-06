from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.security.credentials import contains_secret_material

GoalIntelligenceDecision = Literal["report", "blocked"]
GoalIntelligenceScenario = Literal[
    "status",
    "understand-objective",
    "deep-interview",
    "adaptive-replan",
    "ontology-context",
]

TARGET_VERSION: Final = "v2.2.0"
OBJECTIVE_CONTRACT_ID: Final = "zeus.v2.2.0.goal_intelligence_platform"
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)


class GoalIntelligenceContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: GoalIntelligenceDecision
    target_version: Literal["v2.2.0"] = TARGET_VERSION
    release_stage: Literal["goal_intelligence_platform"] = "goal_intelligence_platform"
    objective_contract_id: Literal["zeus.v2.2.0.goal_intelligence_platform"] = OBJECTIVE_CONTRACT_ID
    scenario: GoalIntelligenceScenario
    blocked_reasons: tuple[str, ...] = ()
    normalized_objective: str = ""
    objective_id: Optional[str] = None
    goal_contract_id: Optional[str] = None
    normalized_goal: str = ""
    acceptance_criteria: tuple[str, ...] = ()
    intent_frame: Optional[dict[str, JsonValue]] = None
    interview_questions: tuple[str, ...] = ()
    interview_question_count: int = 0
    interview_answers: tuple[str, ...] = ()
    interview_round_count: int = 0
    proceed_override_used: bool = False
    residual_assumptions_recorded: bool = False
    cognitive_provider_used: bool = False
    user_context_model: Optional[dict[str, JsonValue]] = None
    goal_intelligence_contract_available: bool = True
    objective_understanding_runtime_available: bool = True
    deep_interview_runtime_available: bool = True
    user_context_model_available: bool = True
    context_ontology_runtime_available: bool = True
    adaptive_replanning_runtime_available: bool = True
    workflow_critic_runtime_available: bool = True
    eval_loop_runtime_available: bool = True
    goal_intelligence_ready: bool = False
    objective_understood: bool = False
    interview_required: bool = False
    deep_interview_ready: bool = False
    user_context_update_candidate: bool = False
    context_ontology_ready: bool = False
    adaptive_replan_ready: bool = False
    workflow_critic_ready: bool = False
    eval_loop_ready: bool = False
    production_ready: bool = False
    objective_contract: Optional[dict[str, JsonValue]] = None
    adaptive_contract: Optional[dict[str, JsonValue]] = None
    memory_contract: Optional[dict[str, JsonValue]] = None
    self_evolution_contract: Optional[dict[str, JsonValue]] = None
    parallel_task_count: int = 0
    ontology_candidate_count: int = 0
    ontology_review_queue_count: int = 0
    eval_record_count: int = 0
    learning_candidate_count: int = 0
    memory_write_executed: bool = False
    workflow_self_modification: bool = False
    workflow_memory_auto_write: bool = False
    workflow_pattern_promoted: bool = False
    memory_auto_promotion: bool = False
    ontology_auto_promotion: bool = False
    wiki_page_update_written: bool = False
    active_skill_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    raw_secret_marker_detected: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> GoalIntelligenceContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True)
        safe = not contains_secret_material(serialized)
        return self.model_copy(update={"no_secret_echo": safe})
