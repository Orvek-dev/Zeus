from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.real_memory_operation_runtime import build_real_memory_operation_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v150_release_gate_reports_memory_operation_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.5.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.5.0"
    assert payload["release_stage"] == "memory_ontology_production_operation"
    assert payload["real_memory_operation_contract_available"] is True
    assert payload["local_memory_operation_available"] is True
    assert payload["ontology_wiki_operation_available"] is True
    assert payload["skill_learning_memory_bridge_available"] is True
    assert payload["retention_delete_operation_available"] is True
    assert payload["memory_secret_quarantine_available"] is True
    assert payload["real_memory_operation_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v1.6.0"
    assert "real_memory_operation_local_store_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_status_reports_surfaces_without_writes() -> None:
    result = build_real_memory_operation_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.5.0"
    assert payload["objective_contract_id"] == "zeus.v1.5.0.memory_ontology_production_operation"
    assert payload["local_memory_store_available"] is True
    assert payload["llm_wiki_view_available"] is True
    assert payload["ontology_review_queue_available"] is True
    assert payload["skill_learning_memory_bridge_available"] is True
    assert payload["memory_write_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_local_store_smoke_writes_reviewable_local_fact() -> None:
    result = build_real_memory_operation_contract(scenario="local-store-smoke")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["local_store_ready"] is True
    assert payload["fact_count"] == 1
    assert payload["memory_write_executed"] is True
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["active_rule_written"] is False
    assert payload["network_opened"] is False
    assert payload["cleanup_performed"] is True
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_ontology_wiki_smoke_reports_review_queue_without_promotion() -> None:
    result = build_real_memory_operation_contract(scenario="ontology-wiki-smoke", subject="Demeter")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["ontology_wiki_ready"] is True
    assert payload["fact_count"] >= 1
    assert payload["wiki_fact_count"] >= 1
    assert payload["memory_ontology_contract"]["wiki_page"]["subject"] == "Demeter"
    assert payload["ontology_auto_promotion"] is False
    assert payload["wiki_page_update_written"] is False
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_secret_quarantine_redacts_raw_secret() -> None:
    result = build_real_memory_operation_contract(scenario="secret-quarantine")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert payload["secret_quarantine_ready"] is True
    assert payload["quarantine_executed"] is True
    assert payload["quarantined_memory_count"] >= 1
    assert "sk-rc6-memory-secret" not in serialized
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_retention_delete_removes_active_fact() -> None:
    result = build_real_memory_operation_contract(scenario="retention-delete")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["retention_delete_ready"] is True
    assert payload["delete_executed"] is True
    assert payload["fact_count"] == 0
    assert payload["deleted_fact_count"] == 1
    assert payload["memory_auto_promotion"] is False
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_skill_learning_bridge_records_reviewable_fact_only() -> None:
    result = build_real_memory_operation_contract(scenario="skill-learning-bridge")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["skill_learning_bridge_ready"] is True
    assert payload["fact_count"] >= 1
    assert payload["skill_learning_memory_contract"]["decision"] == "recorded"
    assert payload["skill_learning_memory_contract"]["memory_promoted"] is False
    assert payload["active_skill_written"] is False
    assert payload["active_rule_written"] is False
    assert payload["authority_widened"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_promotion_block_keeps_authority_closed() -> None:
    result = build_real_memory_operation_contract(scenario="promotion-block")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert payload["promotion_block_ready"] is True
    assert "promotion_requires_review" in payload["blocked_reasons"]
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["active_rule_written"] is False
    assert payload["authority_widened"] is False
    assert payload["no_secret_echo"] is True


def test_real_memory_operation_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "memory-operation",
            "--home",
            str(tmp_path),
            "--scenario",
            "ontology-wiki-smoke",
            "--subject",
            "Zeus",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).memory_operation(scenario="ontology-wiki-smoke", subject="Zeus")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["ontology_wiki_ready"] is True
    assert library_payload["ontology_wiki_ready"] is True
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
