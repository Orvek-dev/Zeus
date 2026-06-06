from __future__ import annotations

import json
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RealSelfEvolutionDecision = Literal["report", "blocked"]
RealSelfEvolutionScenario = Literal[
    "status",
    "eval-learning-smoke",
    "skill-proposal-smoke",
    "workflow-critique-memory",
    "promotion-block",
]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_RAW_SECRET_SPAN_PATTERN: Final = re.compile(
    r"sk-[a-z0-9][a-z0-9._-]*"
    r"|ghp_[a-z0-9_]+"
    r"|github_pat_[a-z0-9_]+"
    r"|glpat-[a-z0-9_-]+"
    r"|xox[abp]-[a-z0-9-]+"
    r"|bearer\s+[a-z0-9._~+/=-]+"
    r"|(api[ _-]?key|private[ _-]?key|token|password|secret)\s*[=:]\s*[^\s\"'}]+"
    r"|(aws_access_key_id|aws_secret_access_key|aws_session_token)\s*[=:]\s*[^\s\"'}]+",
)


class RealSelfEvolutionContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RealSelfEvolutionDecision
    target_version: Literal["v1.6.0"]
    release_stage: Literal["self_evolution_production_loop"]
    objective_contract_id: Literal["zeus.v1.6.0.self_evolution_production_loop"]
    scenario: RealSelfEvolutionScenario
    blocked_reasons: tuple[str, ...] = ()
    real_self_evolution_contract_available: bool = True
    skill_eval_runtime_available: bool = True
    skill_eval_registry_available: bool = True
    skill_evolution_runtime_available: bool = True
    skill_learning_runtime_available: bool = True
    workflow_learning_runtime_available: bool = True
    promotion_review_gate_available: bool = True
    eval_learning_ready: bool = False
    skill_proposal_ready: bool = False
    workflow_critique_memory_ready: bool = False
    promotion_block_ready: bool = False
    real_self_evolution_ready: bool = False
    production_ready: bool = False
    skill_eval_contract: Optional[dict[str, JsonValue]] = None
    skill_eval_registry_contract: Optional[dict[str, JsonValue]] = None
    skill_learning_contract: Optional[dict[str, JsonValue]] = None
    workflow_learning_contract: Optional[dict[str, JsonValue]] = None
    skill_candidate_contract: Optional[dict[str, JsonValue]] = None
    promotion_review_contract: Optional[dict[str, JsonValue]] = None
    eval_record_count: int = 0
    learning_candidate_count: int = 0
    skill_candidate_count: int = 0
    fact_count: int = 0
    eval_record_write_executed: bool = False
    memory_write_executed: bool = False
    workflow_self_modification: bool = False
    workflow_memory_auto_write: bool = False
    workflow_pattern_promoted: bool = False
    memory_auto_promotion: bool = False
    skill_auto_promotion: bool = False
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
    cleanup_performed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RealSelfEvolutionContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = _RAW_SECRET_SPAN_PATTERN.search(serialized) is None
        return self.model_copy(update={"no_secret_echo": safe})
