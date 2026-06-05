from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status
from zeus_agent.stable_release_runtime import build_stable_release_contract


def test_v100_release_gate_reports_stable_governed_live_platform_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0"
    assert payload["release_stage"] == "stable_governed_live_platform"
    assert payload["stable_release_contract_available"] is True
    assert payload["stable_governed_live_platform_ready"] is True
    assert payload["stable_public_release_ready"] is True
    assert payload["production_ready"] is False
    assert payload["live_production_claimed"] is False
    assert payload["next_version"] is None
    assert "stable_governed_live_platform_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_stable_release_contract_reports_governed_platform_without_unrestricted_live_claim() -> None:
    result = build_stable_release_contract()
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0"
    assert payload["stable_release_ready"] is True
    assert payload["governed_live_platform_ready"] is True
    assert payload["production_live_ready"] is False
    assert payload["unrestricted_live_execution_enabled"] is False
    assert payload["provider_owned_client_live_available"] is True
    assert payload["mcp_owned_client_live_available"] is True
    assert payload["mcp_resources_enabled"] is False
    assert payload["mcp_prompts_enabled"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_stable_release_contract_redacts_raw_secret_notes() -> None:
    raw_secret = "token=" + "sk" + "-stable-secret"
    result = build_stable_release_contract(raw_release_note=raw_secret)
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized


def test_stable_release_cli_and_library_match() -> None:
    runner = CliRunner()
    completed = runner.invoke(app, ["stable-release", "--json"])
    library_payload = ZeusAgent().stable_release()

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["stable_release_ready"] is True
    assert library_payload["stable_release_ready"] is True
    assert cli_payload["production_live_ready"] is False
    assert library_payload["production_live_ready"] is False
