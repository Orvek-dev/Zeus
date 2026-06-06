from __future__ import annotations

import json
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RealMemoryOperationDecision = Literal["report", "blocked"]
RealMemoryOperationScenario = Literal[
    "status",
    "local-store-smoke",
    "ontology-wiki-smoke",
    "secret-quarantine",
    "retention-delete",
    "skill-learning-bridge",
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


class RealMemoryOperationContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RealMemoryOperationDecision
    target_version: Literal["v1.5.0"]
    release_stage: Literal["memory_ontology_production_operation"]
    objective_contract_id: Literal["zeus.v1.5.0.memory_ontology_production_operation"]
    scenario: RealMemoryOperationScenario
    blocked_reasons: tuple[str, ...] = ()
    real_memory_operation_contract_available: bool = True
    local_memory_store_available: bool = True
    sqlite_backend_available: bool = True
    memory_privacy_runtime_available: bool = True
    memory_ontology_surface_available: bool = True
    llm_wiki_view_available: bool = True
    ontology_review_queue_available: bool = True
    skill_learning_memory_bridge_available: bool = True
    retention_delete_available: bool = True
    secret_quarantine_available: bool = True
    cross_session_search_default_denied: bool = True
    local_store_ready: bool = False
    ontology_wiki_ready: bool = False
    skill_learning_bridge_ready: bool = False
    retention_delete_ready: bool = False
    secret_quarantine_ready: bool = False
    promotion_block_ready: bool = False
    real_memory_operation_ready: bool = False
    production_ready: bool = False
    memory_privacy_contract: Optional[dict[str, JsonValue]] = None
    memory_ontology_contract: Optional[dict[str, JsonValue]] = None
    skill_learning_memory_contract: Optional[dict[str, JsonValue]] = None
    memory_snapshot: Optional[dict[str, JsonValue]] = None
    fact_count: int = 0
    quarantined_memory_count: int = 0
    deleted_fact_count: int = 0
    ontology_candidate_count: int = 0
    ontology_review_queue_count: int = 0
    wiki_fact_count: int = 0
    memory_write_executed: bool = False
    delete_executed: bool = False
    quarantine_executed: bool = False
    workflow_memory_auto_write: bool = False
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
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    cleanup_performed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RealMemoryOperationContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = _RAW_SECRET_SPAN_PATTERN.search(serialized) is None
        return self.model_copy(update={"no_secret_echo": safe})
