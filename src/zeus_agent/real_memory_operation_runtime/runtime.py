from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final, Optional

from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.memory_ontology_surface_runtime import build_memory_ontology_surface_contract
from zeus_agent.memory_privacy_live_runtime import build_memory_privacy_live_contract
from zeus_agent.real_memory_operation_runtime.models import RealMemoryOperationContract
from zeus_agent.real_memory_operation_runtime.models import RealMemoryOperationDecision
from zeus_agent.real_memory_operation_runtime.models import RealMemoryOperationScenario
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime
from zeus_agent.skill_learning_runtime import SkillLearningMemoryRuntime

_TARGET_VERSION: Final = "v1.5.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.5.0.memory_ontology_production_operation"
_SUPPORTED_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "local-store-smoke",
        "ontology-wiki-smoke",
        "secret-quarantine",
        "retention-delete",
        "skill-learning-bridge",
        "promotion-block",
    },
)


def build_real_memory_operation_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    subject: str = "Zeus",
) -> RealMemoryOperationContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_real_memory_operation_scenario",),
        )
    parsed_scenario = _parse_scenario(safe_scenario)
    if parsed_scenario == "status":
        return _contract(decision="report", scenario="status")
    if home is not None:
        return _build(parsed_scenario, home=home, subject=subject, cleanup_performed=False)
    with tempfile.TemporaryDirectory(prefix="zeus-v150-memory-") as raw_home:
        return _build(parsed_scenario, home=Path(raw_home), subject=subject, cleanup_performed=True)


def _build(
    scenario: RealMemoryOperationScenario,
    *,
    home: Path,
    subject: str,
    cleanup_performed: bool,
) -> RealMemoryOperationContract:
    if scenario == "local-store-smoke":
        return _local_store_smoke(home=home, cleanup_performed=cleanup_performed)
    if scenario == "ontology-wiki-smoke":
        return _ontology_wiki_smoke(home=home, subject=subject, cleanup_performed=cleanup_performed)
    if scenario == "secret-quarantine":
        return _secret_quarantine(home=home, cleanup_performed=cleanup_performed)
    if scenario == "retention-delete":
        return _retention_delete(home=home, cleanup_performed=cleanup_performed)
    if scenario == "skill-learning-bridge":
        return _skill_learning_bridge(home=home, cleanup_performed=cleanup_performed)
    return _promotion_block(home=home, cleanup_performed=cleanup_performed)


def _local_store_smoke(*, home: Path, cleanup_performed: bool) -> RealMemoryOperationContract:
    privacy = build_memory_privacy_live_contract(scenario="local-smoke", home=home).to_payload()
    ready = (
        privacy["decision"] == "report"
        and privacy["local_privacy_ready"] is True
        and privacy["memory_write_executed"] is True
        and privacy["memory_auto_promotion"] is False
        and privacy["ontology_auto_promotion"] is False
        and privacy["no_secret_echo"] is True
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="local-store-smoke",
        blocked_reasons=() if ready else tuple(str(reason) for reason in privacy["blocked_reasons"]),
        memory_privacy_contract=privacy,
        memory_snapshot=_dict_value(privacy.get("memory_snapshot")),
        local_store_ready=ready,
        real_memory_operation_ready=ready,
        fact_count=_int_from_snapshot(privacy.get("memory_snapshot"), "fact_count"),
        quarantined_memory_count=_int_from_snapshot(privacy.get("memory_snapshot"), "quarantined_count"),
        memory_write_executed=bool(privacy["memory_write_executed"]),
        cleanup_performed=cleanup_performed,
    )


def _ontology_wiki_smoke(*, home: Path, subject: str, cleanup_performed: bool) -> RealMemoryOperationContract:
    store = MemoryGraphStore(home)
    store.propose_fact(
        subject=subject,
        predicate="operates_as",
        object_text="Governed local memory and ontology operation.",
        provenance_id="v150.evidence.ontology_wiki",
    )
    surface = build_memory_ontology_surface_contract(home=home, subject=subject).to_payload()
    wiki = surface.get("wiki_page")
    ready = (
        surface["decision"] == "report"
        and surface["memory_fact_count"] >= 1
        and isinstance(wiki, dict)
        and int(wiki.get("fact_count", 0)) >= 1
        and surface["ontology_auto_promotion"] is False
        and surface["no_secret_echo"] is True
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="ontology-wiki-smoke",
        blocked_reasons=() if ready else tuple(str(reason) for reason in surface["blocked_reasons"]),
        memory_ontology_contract=surface,
        memory_snapshot=MemoryGraphStore(home).export_snapshot(),
        ontology_wiki_ready=ready,
        real_memory_operation_ready=ready,
        fact_count=int(surface["memory_fact_count"]),
        quarantined_memory_count=int(surface["quarantined_memory_count"]),
        ontology_candidate_count=int(surface["ontology_candidate_count"]),
        ontology_review_queue_count=int(surface["ontology_review_queue_count"]),
        wiki_fact_count=0 if not isinstance(wiki, dict) else int(wiki.get("fact_count", 0)),
        memory_write_executed=True,
        cleanup_performed=cleanup_performed,
    )


def _secret_quarantine(*, home: Path, cleanup_performed: bool) -> RealMemoryOperationContract:
    privacy = build_memory_privacy_live_contract(scenario="secret-quarantine", home=home).to_payload()
    ready = (
        privacy["decision"] == "blocked"
        and privacy["quarantine_executed"] is True
        and privacy["quarantined_memory_count"] >= 1
        and privacy["no_secret_echo"] is True
    )
    return _contract(
        decision="blocked",
        scenario="secret-quarantine",
        blocked_reasons=tuple(str(reason) for reason in privacy["blocked_reasons"]),
        memory_privacy_contract=privacy,
        memory_snapshot=_dict_value(privacy.get("memory_snapshot")),
        secret_quarantine_ready=ready,
        real_memory_operation_ready=ready,
        quarantined_memory_count=int(privacy["quarantined_memory_count"]),
        memory_write_executed=bool(privacy["memory_write_executed"]),
        quarantine_executed=bool(privacy["quarantine_executed"]),
        cleanup_performed=cleanup_performed,
    )


def _retention_delete(*, home: Path, cleanup_performed: bool) -> RealMemoryOperationContract:
    privacy = build_memory_privacy_live_contract(scenario="delete-retention", home=home).to_payload()
    deleted_snapshot = _dict_value(privacy.get("deleted_snapshot"))
    ready = (
        privacy["decision"] == "report"
        and privacy["delete_executed"] is True
        and _int_from_snapshot(privacy.get("memory_snapshot"), "fact_count") == 0
        and privacy["memory_auto_promotion"] is False
        and privacy["no_secret_echo"] is True
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="retention-delete",
        blocked_reasons=() if ready else tuple(str(reason) for reason in privacy["blocked_reasons"]),
        memory_privacy_contract=privacy,
        memory_snapshot=_dict_value(privacy.get("memory_snapshot")),
        retention_delete_ready=ready,
        real_memory_operation_ready=ready,
        deleted_fact_count=_deleted_count(deleted_snapshot),
        delete_executed=bool(privacy["delete_executed"]),
        cleanup_performed=cleanup_performed,
    )


def _skill_learning_bridge(*, home: Path, cleanup_performed: bool) -> RealMemoryOperationContract:
    eval_result = SkillEvalRuntime(home).evaluate(candidate_id="review-checklist")
    SkillEvalRegistryRuntime(home).record(
        eval_result=eval_result,
        eval_ref="skill-eval://v150/memory-operation",
    )
    bridge = SkillLearningMemoryRuntime(home).record(candidate_id="review-checklist").to_payload()
    ready = (
        bridge["decision"] == "recorded"
        and bridge["fact_count"] >= 1
        and bridge["memory_promoted"] is False
        and bridge["active_skill_written"] is False
        and bridge["active_rule_written"] is False
        and bridge["no_secret_echo"] is True
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="skill-learning-bridge",
        blocked_reasons=() if ready else tuple(str(reason) for reason in bridge["blocked_reasons"]),
        skill_learning_memory_contract=bridge,
        memory_snapshot=MemoryGraphStore(home).export_snapshot(),
        skill_learning_bridge_ready=ready,
        real_memory_operation_ready=ready,
        fact_count=int(bridge["fact_count"]),
        quarantined_memory_count=int(bridge["quarantined_count"]),
        memory_write_executed=ready,
        cleanup_performed=cleanup_performed,
    )


def _promotion_block(*, home: Path, cleanup_performed: bool) -> RealMemoryOperationContract:
    privacy = build_memory_privacy_live_contract(scenario="promotion-block", home=home).to_payload()
    ready = (
        privacy["decision"] == "blocked"
        and "promotion_requires_review" in privacy["blocked_reasons"]
        and privacy["memory_auto_promotion"] is False
        and privacy["ontology_auto_promotion"] is False
        and privacy["active_rule_written"] is False
        and privacy["authority_widened"] is False
        and privacy["no_secret_echo"] is True
    )
    return _contract(
        decision="blocked",
        scenario="promotion-block",
        blocked_reasons=tuple(str(reason) for reason in privacy["blocked_reasons"]),
        memory_privacy_contract=privacy,
        memory_snapshot=_dict_value(privacy.get("memory_snapshot")),
        promotion_block_ready=ready,
        real_memory_operation_ready=ready,
        cleanup_performed=cleanup_performed,
    )


def _contract(
    *,
    decision: RealMemoryOperationDecision,
    scenario: RealMemoryOperationScenario,
    blocked_reasons: tuple[str, ...] = (),
    memory_privacy_contract: Optional[dict] = None,
    memory_ontology_contract: Optional[dict] = None,
    skill_learning_memory_contract: Optional[dict] = None,
    memory_snapshot: Optional[dict] = None,
    local_store_ready: bool = False,
    ontology_wiki_ready: bool = False,
    skill_learning_bridge_ready: bool = False,
    retention_delete_ready: bool = False,
    secret_quarantine_ready: bool = False,
    promotion_block_ready: bool = False,
    real_memory_operation_ready: bool = False,
    fact_count: int = 0,
    quarantined_memory_count: int = 0,
    deleted_fact_count: int = 0,
    ontology_candidate_count: int = 0,
    ontology_review_queue_count: int = 0,
    wiki_fact_count: int = 0,
    memory_write_executed: bool = False,
    delete_executed: bool = False,
    quarantine_executed: bool = False,
    cleanup_performed: bool = False,
) -> RealMemoryOperationContract:
    return RealMemoryOperationContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="memory_ontology_production_operation",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        local_store_ready=local_store_ready,
        ontology_wiki_ready=ontology_wiki_ready,
        skill_learning_bridge_ready=skill_learning_bridge_ready,
        retention_delete_ready=retention_delete_ready,
        secret_quarantine_ready=secret_quarantine_ready,
        promotion_block_ready=promotion_block_ready,
        real_memory_operation_ready=real_memory_operation_ready,
        production_ready=False,
        memory_privacy_contract=memory_privacy_contract,
        memory_ontology_contract=memory_ontology_contract,
        skill_learning_memory_contract=skill_learning_memory_contract,
        memory_snapshot=memory_snapshot,
        fact_count=fact_count,
        quarantined_memory_count=quarantined_memory_count,
        deleted_fact_count=deleted_fact_count,
        ontology_candidate_count=ontology_candidate_count,
        ontology_review_queue_count=ontology_review_queue_count,
        wiki_fact_count=wiki_fact_count,
        memory_write_executed=memory_write_executed,
        delete_executed=delete_executed,
        quarantine_executed=quarantine_executed,
        workflow_memory_auto_write=False,
        memory_auto_promotion=False,
        ontology_auto_promotion=False,
        wiki_page_update_written=False,
        active_skill_written=False,
        active_rule_written=False,
        authority_widened=False,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
        cleanup_performed=cleanup_performed,
    ).with_secret_scan()


def _parse_scenario(value: str) -> RealMemoryOperationScenario:
    if value == "status":
        return "status"
    if value == "local-store-smoke":
        return "local-store-smoke"
    if value == "ontology-wiki-smoke":
        return "ontology-wiki-smoke"
    if value == "secret-quarantine":
        return "secret-quarantine"
    if value == "retention-delete":
        return "retention-delete"
    if value == "skill-learning-bridge":
        return "skill-learning-bridge"
    return "promotion-block"


def _dict_value(value: object) -> Optional[dict]:
    if isinstance(value, dict):
        return value
    return None


def _int_from_snapshot(value: object, key: str) -> int:
    if not isinstance(value, dict):
        return 0
    item = value.get(key)
    if isinstance(item, int) and not isinstance(item, bool):
        return item
    return 0


def _deleted_count(snapshot: Optional[dict]) -> int:
    facts = () if snapshot is None else snapshot.get("facts", ())
    if not isinstance(facts, list):
        return 0
    return sum(1 for fact in facts if isinstance(fact, dict) and fact.get("status") == "deleted")
