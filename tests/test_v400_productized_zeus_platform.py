from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.productized_zeus_platform_runtime import build_productized_zeus_platform_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v400_release_gate_reports_productized_platform_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v4.0.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v4.0.0"
    assert payload["release_stage"] == "productized_zeus_platform"
    assert payload["productized_zeus_platform_contract_available"] is True
    assert payload["productized_zeus_platform_ready"] is True
    assert payload["zeus_persona_cli_available"] is True
    assert payload["setup_wizard_available"] is True
    assert payload["status_cockpit_available"] is True
    assert payload["installable_user_journey_available"] is True
    assert payload["operator_command_map_available"] is True
    assert payload["productized_operator_command_map_available"] is True
    assert payload["production_ready"] is False
    assert payload["next_version"] is None


def test_status_aggregates_product_surfaces_without_live_side_effects(tmp_path: Path) -> None:
    payload = build_productized_zeus_platform_contract(scenario="status", home=tmp_path).to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v4.0.0"
    assert payload["productized_zeus_platform_ready"] is True
    assert payload["zeus_call_response"] == "네, 제우스입니다."
    assert payload["setup_wizard_ready"] is True
    assert payload["status_cockpit_ready"] is True
    assert payload["cognitive_provider_activation_ready"] is True
    assert payload["plugin_ecosystem_ready"] is True
    assert payload["tenant_auth_ready"] is True
    assert payload["candidate_learning_ready"] is True
    assert payload["settings_written"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_public_boundary_blocks_production_live_execution(tmp_path: Path) -> None:
    payload = build_productized_zeus_platform_contract(scenario="public-boundary", home=tmp_path).to_payload()

    assert payload["decision"] == "blocked"
    assert "production_live_execution_not_enabled" in payload["blocked_reasons"]
    assert payload["public_boundary_ready"] is True
    assert payload["production_live_ready"] is False
    assert payload["unrestricted_live_execution_enabled"] is False
    assert payload["external_provider_enabled"] is False
    assert payload["mcp_remote_server_enabled"] is False
    assert payload["remote_sandbox_execution_enabled"] is False


def test_secret_like_operator_note_blocks_without_echo() -> None:
    raw_secret = "token=" + "sk" + "-productized-secret"
    payload = build_productized_zeus_platform_contract(operator_note=raw_secret).to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert raw_secret not in serialized
    assert payload["no_secret_echo"] is True


def test_cli_and_library_expose_productized_platform(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        ["productized-platform", "--home", str(tmp_path), "--scenario", "status", "--json"],
    )
    cli_payload = json.loads(completed.stdout)
    library_payload = ZeusAgent(home=tmp_path).productized_platform_runtime(scenario="status")

    assert completed.exit_code == 0, completed.stdout
    assert cli_payload["target_version"] == "v4.0.0"
    assert library_payload["target_version"] == "v4.0.0"
    assert cli_payload["productized_zeus_platform_ready"] is True
    assert library_payload["productized_zeus_platform_ready"] is True
