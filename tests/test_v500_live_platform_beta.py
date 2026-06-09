from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_platform_beta_runtime import build_live_platform_beta
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v500_release_gate_reports_productized_live_platform_beta() -> None:
    payload = build_release_gated_ulw_status(target_version="v5.0.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v5.0.0"
    assert payload["release_stage"] == "productized_live_platform_beta"
    assert payload["productized_live_platform_beta_contract_available"] is True
    assert payload["objective_to_live_beta_journey_available"] is True
    assert payload["authority_ux_beta_available"] is True
    assert payload["public_beta_boundary_available"] is True
    assert payload["productized_live_platform_beta_ready"] is True
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v5.5.0"


def test_live_platform_beta_status_aggregates_installable_operator_journey(tmp_path: Path) -> None:
    payload = build_live_platform_beta(home=tmp_path, scenario="status").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v5.0.0"
    assert payload["zeus_call_response"] == "네, 제우스입니다."
    assert payload["productized_live_platform_beta_ready"] is True
    assert payload["objective_execution_spine_ready"] is True
    assert payload["governed_live_slice_ready"] is True
    assert payload["authority_ux_ready"] is True
    assert payload["operator_journey_ready"] is True
    assert payload["cli_surface_ready"] is True
    assert payload["python_library_surface_ready"] is True
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_live_platform_beta_public_boundary_blocks_production_claim(tmp_path: Path) -> None:
    payload = build_live_platform_beta(home=tmp_path, scenario="public-boundary").to_payload()

    assert payload["decision"] == "blocked"
    assert "production_live_execution_not_enabled" in payload["blocked_reasons"]
    assert payload["public_beta_boundary_ready"] is True
    assert payload["production_ready"] is False
    assert payload["external_provider_enabled"] is False
    assert payload["remote_mcp_enabled"] is False
    assert payload["remote_sandbox_enabled"] is False


def test_live_platform_beta_operator_demo_exposes_commands_without_side_effects(tmp_path: Path) -> None:
    payload = build_live_platform_beta(home=tmp_path, scenario="operator-demo").to_payload()

    assert payload["decision"] == "report"
    assert "zeus objective-start" in payload["operator_commands"][0]
    assert any("zeus governed-live-slice" in command for command in payload["operator_commands"])
    assert payload["operator_journey_ready"] is True
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False


def test_cli_and_library_expose_live_platform_beta(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        ["live-platform-beta", "--home", str(tmp_path), "--scenario", "status", "--json"],
    )
    library_payload = ZeusAgent(home=tmp_path).live_platform_beta(scenario="status")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == "v5.0.0"
    assert library_payload["target_version"] == "v5.0.0"
    assert cli_payload["productized_live_platform_beta_ready"] is True
    assert library_payload["productized_live_platform_beta_ready"] is True
