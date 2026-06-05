from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.memory_cockpit_runtime import MemoryCockpitRuntime
from zeus_agent.ontology_cockpit_runtime import OntologyCockpitRuntime

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_TARGET_VERSION: Final = "v0.9.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v0.9.0.memory_ontology"
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
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class MemoryOntologySurfaceResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    target_version: str
    objective_contract_id: str
    selected_subject: Optional[str]
    selected_candidate_id: Optional[str]
    memory_fact_count: int
    quarantined_memory_count: int
    ontology_candidate_count: int
    ontology_proposed_count: int
    ontology_blocked_count: int
    ontology_promoted_count: int
    ontology_review_queue_count: int
    wiki_page: Optional[dict[str, JsonValue]]
    selected_ontology_candidate: Optional[dict[str, JsonValue]]
    blocked_reasons: tuple[str, ...] = ()
    memory_store_local: bool = True
    memory_storage_backend: Literal["sqlite_local"] = "sqlite_local"
    local_store_schema_ensured: bool = True
    report_command_may_initialize_local_store: bool = True
    memory_graph_contract_available: bool = True
    llm_wiki_contract_available: bool = True
    ontology_review_contract_available: bool = True
    skill_learning_memory_contract_available: bool = True
    retention_policy_contract_available: bool = True
    retention_policy: Literal["local_review_required"] = "local_review_required"
    memory_auto_promotion: bool = False
    ontology_auto_promotion: bool = False
    wiki_page_update_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    live_production_claimed: bool = False
    raw_secret_marker_detected: bool = False
    no_secret_echo: bool = True
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> MemoryOntologySurfaceResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_memory_ontology_surface_contract(
    *,
    home: Path,
    subject: Optional[str] = None,
    candidate_id: Optional[str] = None,
) -> MemoryOntologySurfaceResult:
    subject_selector = _selector(subject)
    candidate_selector = _selector(candidate_id)
    secret_marker_detected = subject_selector.secret_detected or candidate_selector.secret_detected
    memory = MemoryCockpitRuntime(home).build(subject=subject_selector.runtime_value)
    ontology = OntologyCockpitRuntime(home).build(candidate_id=candidate_selector.runtime_value)
    blocked_reasons = _blocked_reasons(
        secret_marker_detected=secret_marker_detected,
        ontology_blocked_reasons=ontology.blocked_reasons,
    )
    result = MemoryOntologySurfaceResult(
        decision="blocked" if blocked_reasons else "report",
        target_version=_TARGET_VERSION,
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        selected_subject=subject_selector.public_value,
        selected_candidate_id=candidate_selector.public_value,
        memory_fact_count=memory.fact_count,
        quarantined_memory_count=memory.quarantined_count,
        ontology_candidate_count=ontology.candidate_count,
        ontology_proposed_count=ontology.proposed_candidate_count,
        ontology_blocked_count=ontology.blocked_candidate_count,
        ontology_promoted_count=ontology.promoted_candidate_count,
        ontology_review_queue_count=ontology.review_queue_count,
        wiki_page=memory.wiki_page,
        selected_ontology_candidate=ontology.selected_candidate,
        blocked_reasons=blocked_reasons,
        memory_store_local=True,
        local_store_schema_ensured=True,
        report_command_may_initialize_local_store=True,
        retention_policy=memory.retention_policy,
        memory_auto_promotion=False,
        ontology_auto_promotion=False,
        wiki_page_update_written=False,
        active_rule_written=False,
        authority_widened=False,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        live_production_claimed=False,
        raw_secret_marker_detected=secret_marker_detected,
        recommended_next_commands=_recommended_next_commands(
            subject=subject_selector.public_value,
            candidate_id=candidate_selector.public_value,
            blocked=bool(blocked_reasons),
        ),
    )
    return result.with_secret_scan()


class _Selector(BaseModel):
    model_config = _MODEL_CONFIG

    runtime_value: Optional[str]
    public_value: Optional[str]
    secret_detected: bool


def _selector(value: Optional[str]) -> _Selector:
    if value is None:
        return _Selector(runtime_value=None, public_value=None, secret_detected=False)
    normalized = value.strip()
    if not normalized:
        return _Selector(runtime_value=None, public_value=None, secret_detected=False)
    if _has_secret_marker(normalized):
        return _Selector(runtime_value=None, public_value="unknown", secret_detected=True)
    return _Selector(runtime_value=normalized, public_value=normalized, secret_detected=False)


def _blocked_reasons(
    *,
    secret_marker_detected: bool,
    ontology_blocked_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = []
    if secret_marker_detected:
        reasons.append("raw_secret_marker_detected")
    reasons.extend(ontology_blocked_reasons)
    return tuple(reasons)


def _recommended_next_commands(
    *,
    subject: Optional[str],
    candidate_id: Optional[str],
    blocked: bool,
) -> tuple[str, ...]:
    if blocked:
        return (
            "zeus remember --json",
            "zeus ontology --json",
            "zeus security --json",
        )
    if subject is not None:
        return (
            "zeus remember --subject {0} --json".format(subject),
            "zeus wiki-page --subject {0} --json".format(subject),
            "zeus ontology --json",
        )
    if candidate_id is not None:
        return (
            "zeus ontology --candidate-id {0} --json".format(candidate_id),
            "zeus remember --json",
            "zeus skills --json",
        )
    return (
        "zeus remember --json",
        "zeus ontology --json",
        "zeus skill-learnings --json",
    )


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
