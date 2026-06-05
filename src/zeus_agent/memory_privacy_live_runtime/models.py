from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

MemoryPrivacyLiveDecision = Literal["report", "blocked"]
MemoryPrivacyLiveScenario = Literal[
    "status",
    "local-smoke",
    "secret-quarantine",
    "delete-retention",
    "promotion-block",
]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)


class MemoryPrivacyLiveContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: MemoryPrivacyLiveDecision
    target_version: str
    release_stage: Literal["memory_privacy_live"]
    objective_contract_id: str
    scenario: MemoryPrivacyLiveScenario
    blocked_reasons: tuple[str, ...] = ()
    memory_privacy_live_contract_available: bool = True
    local_memory_store_available: bool = True
    sqlite_backend_available: bool = True
    retention_delete_available: bool = True
    secret_quarantine_available: bool = True
    pii_redaction_available: bool = True
    cross_session_search_default_denied: bool = True
    memory_store_local: bool = True
    memory_storage_backend: Literal["sqlite_local"] = "sqlite_local"
    local_store_schema_ensured: bool = False
    local_privacy_ready: bool = False
    production_ready: bool = False
    memory_write_executed: bool = False
    delete_executed: bool = False
    quarantine_executed: bool = False
    redacted_object_available: bool = False
    quarantined_memory_count: int = 0
    memory_snapshot: Optional[dict[str, JsonValue]] = None
    deleted_snapshot: Optional[dict[str, JsonValue]] = None
    deleted_fact: Optional[dict[str, JsonValue]] = None
    surface_contract: Optional[dict[str, JsonValue]] = None
    workflow_memory_auto_write: bool = False
    memory_auto_promotion: bool = False
    ontology_auto_promotion: bool = False
    wiki_page_update_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    raw_secret_marker_detected: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> MemoryPrivacyLiveContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})
