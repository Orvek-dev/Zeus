from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.installable_live_platform_runtime import build_installable_live_platform_contract
from zeus_agent.library_runtime.agent import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v230_release_gate_reports_installable_live_platform_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v2.3.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v2.3.0"
    assert payload["release_stage"] == "installable_live_platform"
    assert payload["installable_live_platform_contract_available"] is True
    assert payload["cli_install_surface_available"] is True
    assert payload["python_library_install_surface_available"] is True
    assert payload["plugin_manifest_install_surface_available"] is True
    assert payload["remote_sandbox_policy_install_surface_available"] is True
    assert payload["installable_live_platform_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v2.4.0"


def test_status_reports_installable_platform_without_live_side_effects(tmp_path: Path) -> None:
    result = build_installable_live_platform_contract(scenario="status", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v2.3.0"
    assert payload["installable_live_platform_ready"] is True
    assert payload["production_ready"] is False
    assert payload["provider_install_surface_available"] is True
    assert payload["mcp_install_surface_available"] is True
    assert payload["gateway_install_surface_available"] is True
    assert payload["api_install_surface_available"] is True
    assert payload["plugin_manifest_install_surface_available"] is True
    assert payload["remote_sandbox_policy_install_surface_available"] is True
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False


def test_plugin_manifest_scenario_keeps_plugin_quarantined(tmp_path: Path) -> None:
    result = build_installable_live_platform_contract(scenario="plugin-manifest", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["plugin_manifest_install_surface_available"] is True
    assert payload["plugin_manifest_contract"]["decision"] == "quarantined"
    assert payload["plugin_manifest_contract"]["tool_registration_allowed"] is False
    assert payload["active_rule_written"] is False
    assert payload["handler_executed"] is False


def test_remote_sandbox_policy_scenario_blocks_remote_execution(tmp_path: Path) -> None:
    result = build_installable_live_platform_contract(scenario="remote-sandbox-policy", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "remote_sandbox_blocked" in payload["blocked_reasons"]
    assert payload["remote_sandbox_policy_install_surface_available"] is True
    assert payload["remote_sandbox_execution_opened"] is False
    assert payload["network_opened"] is False


def test_cli_and_library_expose_installable_live_platform(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        ["installable-live-platform", "--home", str(tmp_path), "--scenario", "status", "--json"],
    )
    cli_payload = json.loads(completed.stdout)
    library_payload = ZeusAgent(home=tmp_path).installable_live_platform_runtime(scenario="status")

    assert completed.exit_code == 0
    assert cli_payload["target_version"] == "v2.3.0"
    assert cli_payload["installable_live_platform_ready"] is True
    assert library_payload["target_version"] == "v2.3.0"
    assert library_payload["installable_live_platform_ready"] is True
