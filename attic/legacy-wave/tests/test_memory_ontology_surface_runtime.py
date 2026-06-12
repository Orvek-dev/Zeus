from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.memory_ontology_surface_runtime import build_memory_ontology_surface_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v090_release_gate_reports_memory_ontology_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v0.9.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.9.0"
    assert payload["release_stage"] == "memory_ontology"
    assert payload["memory_ontology_contract_available"] is True
    assert payload["memory_graph_contract_available"] is True
    assert payload["llm_wiki_contract_available"] is True
    assert payload["ontology_review_contract_available"] is True
    assert payload["skill_learning_memory_contract_available"] is True
    assert payload["retention_policy_contract_available"] is True
    assert payload["memory_ontology_ready"] is False
    assert "memory_ontology_release_gate_manual_qa" in payload["required_checkpoint_evidence"]
    assert "memory_ontology_secret_boundary_manual_qa" in payload["required_checkpoint_evidence"]
    assert "platform_surface_release_gate_manual_qa" not in payload["required_checkpoint_evidence"]
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["active_rule_written"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["next_version"] == "v0.10.0"
    assert payload["no_secret_echo"] is True


def test_memory_ontology_surface_reports_local_memory_wiki_and_review_queue(tmp_path: Path) -> None:
    MemoryGraphStore(tmp_path).propose_fact(
        subject="Zeus",
        predicate="core_value",
        object_text="Purpose-oriented governed execution.",
        provenance_id="v090.evidence.memory",
    )

    result = build_memory_ontology_surface_contract(home=tmp_path, subject="Zeus")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.9.0"
    assert payload["objective_contract_id"] == "zeus.v0.9.0.memory_ontology"
    assert payload["memory_store_local"] is True
    assert payload["memory_storage_backend"] == "sqlite_local"
    assert payload["local_store_schema_ensured"] is True
    assert payload["report_command_may_initialize_local_store"] is True
    assert payload["memory_graph_contract_available"] is True
    assert payload["llm_wiki_contract_available"] is True
    assert payload["ontology_review_contract_available"] is True
    assert payload["retention_policy"] == "local_review_required"
    assert payload["selected_subject"] == "Zeus"
    assert payload["memory_fact_count"] == 1
    assert payload["quarantined_memory_count"] == 0
    assert payload["wiki_page"]["fact_count"] == 1
    assert "Purpose-oriented governed execution." in payload["wiki_page"]["body"]
    assert payload["ontology_candidate_count"] >= 2
    assert payload["ontology_promoted_count"] == 0
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["wiki_page_update_written"] is False
    assert payload["active_rule_written"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_memory_ontology_cli_and_library_surface_match(tmp_path: Path) -> None:
    MemoryGraphStore(tmp_path).propose_fact(
        subject="Demeter",
        predicate="governs",
        object_text="Local durable memory and ontology review.",
        provenance_id="v090.evidence.library",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "memory-ontology",
            "--home",
            str(tmp_path),
            "--subject",
            "Demeter",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).memory_ontology_status(subject="Demeter")

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == library_payload
    assert library_payload["decision"] == "report"
    assert library_payload["wiki_page"]["fact_count"] == 1
    assert library_payload["memory_store_local"] is True


def test_memory_ontology_surface_blocks_secret_like_selectors_without_echo(tmp_path: Path) -> None:
    raw_secret = "".join(("sk", "-", "v090-memory-secret"))
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "memory-ontology",
            "--home",
            str(tmp_path),
            "--subject",
            raw_secret,
            "--candidate-id",
            raw_secret,
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True).lower()
    assert payload["decision"] == "blocked"
    assert payload["selected_subject"] == "unknown"
    assert payload["selected_candidate_id"] == "unknown"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized
