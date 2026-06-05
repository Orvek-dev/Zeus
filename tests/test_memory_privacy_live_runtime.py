from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.memory_privacy_live_runtime import build_memory_privacy_live_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v100rc6_release_gate_reports_memory_privacy_live_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.6")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.6"
    assert payload["release_stage"] == "memory_privacy_live"
    assert payload["memory_privacy_live_contract_available"] is True
    assert payload["local_memory_store_available"] is True
    assert payload["sqlite_backend_available"] is True
    assert payload["retention_delete_available"] is True
    assert payload["secret_quarantine_available"] is True
    assert payload["pii_redaction_available"] is True
    assert payload["cross_session_search_default_denied"] is True
    assert payload["local_privacy_ready"] is False
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["wiki_page_update_written"] is False
    assert payload["active_rule_written"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] is None
    assert "memory_privacy_live_secret_quarantine_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_memory_privacy_live_status_reports_contract_without_side_effects(tmp_path: Path) -> None:
    result = build_memory_privacy_live_contract(scenario="status", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.6"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.6.memory_privacy_live"
    assert payload["scenario"] == "status"
    assert payload["local_privacy_ready"] is False
    assert payload["memory_write_executed"] is False
    assert payload["delete_executed"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True
    assert not (tmp_path / "memory-graph.sqlite3").exists()


def test_memory_privacy_live_local_smoke_writes_local_fact_without_promotion(tmp_path: Path) -> None:
    result = build_memory_privacy_live_contract(scenario="local-smoke", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["local_privacy_ready"] is True
    assert payload["memory_write_executed"] is True
    assert payload["memory_store_local"] is True
    assert payload["memory_storage_backend"] == "sqlite_local"
    assert payload["local_store_schema_ensured"] is True
    assert payload["memory_snapshot"]["fact_count"] == 1
    assert payload["surface_contract"]["memory_fact_count"] == 1
    assert payload["surface_contract"]["wiki_page"]["fact_count"] == 1
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["wiki_page_update_written"] is False
    assert payload["active_rule_written"] is False
    assert payload["cross_session_search_default_denied"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_memory_privacy_live_secret_quarantine_redacts_raw_secret(tmp_path: Path) -> None:
    raw_secret = "".join(("sk", "-", "rc6-memory-secret"))
    result = build_memory_privacy_live_contract(scenario="secret-quarantine", home=tmp_path)
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "blocked"
    assert payload["secret_quarantine_available"] is True
    assert payload["quarantine_executed"] is True
    assert payload["quarantined_memory_count"] == 1
    assert payload["memory_snapshot"]["quarantined_count"] == 1
    assert payload["redacted_object_available"] is True
    assert raw_secret not in serialized
    assert "secret_like_content" in payload["blocked_reasons"]
    assert payload["memory_auto_promotion"] is False
    assert payload["active_rule_written"] is False
    assert payload["no_secret_echo"] is True


def test_memory_privacy_live_delete_retention_removes_active_fact(tmp_path: Path) -> None:
    result = build_memory_privacy_live_contract(scenario="delete-retention", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["retention_delete_available"] is True
    assert payload["delete_executed"] is True
    assert payload["deleted_fact"]["status"] == "deleted"
    assert payload["deleted_fact"]["object_text"] == "[deleted]"
    assert payload["memory_snapshot"]["fact_count"] == 0
    assert payload["deleted_snapshot"]["fact_count"] == 0
    assert payload["deleted_snapshot"]["facts"][0]["status"] == "deleted"
    assert payload["memory_auto_promotion"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_memory_privacy_live_promotion_block_never_writes_active_authority(tmp_path: Path) -> None:
    result = build_memory_privacy_live_contract(scenario="promotion-block", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "promotion_requires_review" in payload["blocked_reasons"]
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["wiki_page_update_written"] is False
    assert payload["active_rule_written"] is False
    assert payload["authority_widened"] is False
    assert payload["workflow_memory_auto_write"] is False
    assert payload["local_privacy_ready"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_memory_privacy_live_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "memory-privacy-live",
            "--scenario",
            "local-smoke",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).memory_privacy_live(scenario="local-smoke")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["local_privacy_ready"] is True
    assert library_payload["local_privacy_ready"] is True
    assert cli_payload["cross_session_search_default_denied"] is True
    assert cli_payload["no_secret_echo"] is True
