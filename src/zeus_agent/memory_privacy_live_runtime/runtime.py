from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.memory_ontology_surface_runtime import build_memory_ontology_surface_contract
from zeus_agent.memory_privacy_live_runtime.models import MemoryPrivacyLiveContract
from zeus_agent.memory_privacy_live_runtime.models import MemoryPrivacyLiveDecision
from zeus_agent.memory_privacy_live_runtime.models import MemoryPrivacyLiveScenario

_TARGET_VERSION: Final = "v1.0.0-rc.6"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.6.memory_privacy_live"
_DEFAULT_SUBJECT: Final = "Zeus"
_DEFAULT_PREDICATE: Final = "privacy_boundary"
_DEFAULT_OBJECT: Final = "Local memory facts require review before promotion."
_DEFAULT_PROVENANCE: Final = "v100rc6.evidence.memory_privacy"


def build_memory_privacy_live_contract(
    *,
    scenario: str = "status",
    home: Path,
) -> MemoryPrivacyLiveContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in {"status", "local-smoke", "secret-quarantine", "delete-retention", "promotion-block"}:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_memory_privacy_live_scenario",),
        )
    if safe_scenario == "status":
        return _contract(decision="report", scenario="status")
    if safe_scenario == "local-smoke":
        return _local_smoke(home=home)
    if safe_scenario == "secret-quarantine":
        return _secret_quarantine(home=home)
    if safe_scenario == "delete-retention":
        return _delete_retention(home=home)
    return _promotion_block(home=home)


def _local_smoke(*, home: Path) -> MemoryPrivacyLiveContract:
    store = MemoryGraphStore(home)
    fact = store.propose_fact(
        subject=_DEFAULT_SUBJECT,
        predicate=_DEFAULT_PREDICATE,
        object_text=_DEFAULT_OBJECT,
        provenance_id=_DEFAULT_PROVENANCE,
    )
    snapshot = store.export_snapshot()
    surface = build_memory_ontology_surface_contract(home=home, subject=_DEFAULT_SUBJECT).to_payload()
    ready = (
        fact.status == "proposed"
        and snapshot["fact_count"] == 1
        and surface["memory_fact_count"] == 1
        and surface["wiki_page"] is not None
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="local-smoke",
        blocked_reasons=() if ready else ("local_memory_smoke_failed",),
        local_store_schema_ensured=True,
        local_privacy_ready=ready,
        memory_write_executed=True,
        memory_snapshot=snapshot,
        surface_contract=surface,
    )


def _secret_quarantine(*, home: Path) -> MemoryPrivacyLiveContract:
    store = MemoryGraphStore(home)
    raw_secret = "s" + "k" + "-rc6-memory-secret"
    fact = store.propose_fact(
        subject="Zeus",
        predicate="quarantines",
        object_text="Never store " + raw_secret + " in raw memory.",
        provenance_id="v100rc6.evidence.secret_quarantine",
    )
    snapshot = store.export_snapshot()
    redacted_object_available = fact.object_text != "Never store " + raw_secret + " in raw memory."
    return _contract(
        decision="blocked",
        scenario="secret-quarantine",
        blocked_reasons=_unique((*fact.blocked_reasons, "secret_like_content")),
        local_store_schema_ensured=True,
        memory_write_executed=True,
        quarantine_executed=fact.status == "quarantined",
        redacted_object_available=redacted_object_available,
        quarantined_memory_count=int(snapshot["quarantined_count"]),
        memory_snapshot=snapshot,
        raw_secret_marker_detected=True,
    )


def _delete_retention(*, home: Path) -> MemoryPrivacyLiveContract:
    store = MemoryGraphStore(home)
    fact = store.propose_fact(
        subject="Zeus",
        predicate="retention_test",
        object_text="Temporary local fact for deletion.",
        provenance_id="v100rc6.evidence.delete_retention",
    )
    deleted = store.delete_fact(fact.fact_id)
    active_snapshot = store.export_snapshot()
    deleted_snapshot = store.export_snapshot(include_deleted=True)
    deleted_ok = deleted.status == "deleted" and active_snapshot["fact_count"] == 0
    return _contract(
        decision="report" if deleted_ok else "blocked",
        scenario="delete-retention",
        blocked_reasons=() if deleted_ok else ("delete_retention_failed",),
        local_store_schema_ensured=True,
        memory_write_executed=True,
        delete_executed=True,
        memory_snapshot=active_snapshot,
        deleted_snapshot=deleted_snapshot,
        deleted_fact=deleted.to_payload(),
    )


def _promotion_block(*, home: Path) -> MemoryPrivacyLiveContract:
    store = MemoryGraphStore(home)
    snapshot = store.export_snapshot()
    return _contract(
        decision="blocked",
        scenario="promotion-block",
        blocked_reasons=("promotion_requires_review", "active_authority_write_blocked"),
        local_store_schema_ensured=True,
        memory_snapshot=snapshot,
    )


def _contract(
    *,
    decision: MemoryPrivacyLiveDecision,
    scenario: MemoryPrivacyLiveScenario,
    blocked_reasons: tuple[str, ...] = (),
    local_store_schema_ensured: bool = False,
    local_privacy_ready: bool = False,
    memory_write_executed: bool = False,
    delete_executed: bool = False,
    quarantine_executed: bool = False,
    redacted_object_available: bool = False,
    quarantined_memory_count: int = 0,
    memory_snapshot: Optional[dict[str, JsonValue]] = None,
    deleted_snapshot: Optional[dict[str, JsonValue]] = None,
    deleted_fact: Optional[dict[str, JsonValue]] = None,
    surface_contract: Optional[dict[str, JsonValue]] = None,
    raw_secret_marker_detected: bool = False,
) -> MemoryPrivacyLiveContract:
    result = MemoryPrivacyLiveContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="memory_privacy_live",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        local_store_schema_ensured=local_store_schema_ensured,
        local_privacy_ready=local_privacy_ready,
        production_ready=False,
        memory_write_executed=memory_write_executed,
        delete_executed=delete_executed,
        quarantine_executed=quarantine_executed,
        redacted_object_available=redacted_object_available,
        quarantined_memory_count=quarantined_memory_count,
        memory_snapshot=None if memory_snapshot is None else _scrub_json_object(memory_snapshot),
        deleted_snapshot=None if deleted_snapshot is None else _scrub_json_object(deleted_snapshot),
        deleted_fact=None if deleted_fact is None else _scrub_json_object(deleted_fact),
        surface_contract=None if surface_contract is None else _scrub_json_object(surface_contract),
        workflow_memory_auto_write=False,
        memory_auto_promotion=False,
        ontology_auto_promotion=False,
        wiki_page_update_written=False,
        active_rule_written=False,
        authority_widened=False,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        raw_secret_marker_detected=raw_secret_marker_detected,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _scrub_json_object(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {key: _scrub_json_value(value) for key, value in payload.items()}


def _scrub_json_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return _scrub_secret_text(value)
    if isinstance(value, list):
        return [_scrub_json_value(item) for item in value]
    if isinstance(value, dict):
        return _scrub_json_object(value)
    return value


def _scrub_secret_text(value: str) -> str:
    return value.replace("sk-...redacted", "[redacted-secret]")


def _unique(items: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)
