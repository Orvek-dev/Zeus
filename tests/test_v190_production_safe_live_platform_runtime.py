from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.production_safe_live_platform_runtime import build_production_safe_live_platform_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v190_release_gate_reports_production_safe_connection_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.9.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.9.0"
    assert payload["release_stage"] == "production_safe_live_platform_connections"
    assert payload["production_safe_live_platform_contract_available"] is True
    assert payload["live_connector_activation_layer_available"] is True
    assert payload["external_provider_connection_available"] is True
    assert payload["mcp_production_connection_available"] is True
    assert payload["hosted_api_connection_available"] is True
    assert payload["gateway_daemon_connection_available"] is True
    assert payload["browser_live_connection_available"] is True
    assert payload["terminal_sandbox_connection_available"] is True
    assert payload["production_safe_connections_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v2.0.0"
    assert "production_safe_live_platform_status_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_production_safe_live_platform_status_maps_all_live_connectors(tmp_path: Path) -> None:
    result = build_production_safe_live_platform_contract(scenario="status", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.9.0"
    assert payload["objective_contract_id"] == "zeus.v1.9.0.production_safe_live_platform_connections"
    assert payload["connection_surface_count"] >= 6
    assert payload["production_safe_connections_ready"] is True
    assert payload["activation_contract"]["activation_contract_ready"] is True
    assert payload["provider_contract"]["decision"] == "report"
    assert payload["mcp_contract"]["decision"] == "report"
    assert payload["platform_contract"]["api_dry_run_ready"] is True
    assert payload["execution_contract"]["terminal_facade_available"] is True
    assert payload["production_ready"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_production_safe_live_platform_provider_mcp_smoke_keeps_remote_execution_governed(tmp_path: Path) -> None:
    result = build_production_safe_live_platform_contract(scenario="provider-mcp-smoke", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["provider_connection_ready"] is True
    assert payload["mcp_connection_ready"] is True
    assert payload["provider_contract"]["real_provider_runtime_ready"] is False
    assert payload["mcp_contract"]["mcp_setup_dry_run_available"] is True
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True


def test_production_safe_live_platform_boundary_blocks_gateway_browser_remote(tmp_path: Path) -> None:
    result = build_production_safe_live_platform_contract(scenario="platform-execution-boundary", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert payload["platform_boundary_ready"] is True
    assert "external_gateway_delivery_blocked" in payload["blocked_reasons"]
    assert "browser_live_navigation_blocked" in payload["blocked_reasons"]
    assert "remote_sandbox_blocked" in payload["blocked_reasons"]
    assert payload["gateway_daemon_started"] is False
    assert payload["browser_navigation_opened"] is False
    assert payload["remote_sandbox_opened"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_production_safe_live_platform_activation_required_blocks_missing_lease(tmp_path: Path) -> None:
    result = build_production_safe_live_platform_contract(scenario="activation-required-block", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "runtime_lease_required" in payload["blocked_reasons"]
    assert payload["activation_contract"]["activation_contract_ready"] is False
    assert payload["production_safe_connections_ready"] is False
    assert payload["production_ready"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_production_safe_live_platform_secret_marker_is_blocked_without_echo(tmp_path: Path) -> None:
    result = build_production_safe_live_platform_contract(
        scenario="status",
        home=tmp_path,
        operator_note="operator pasted sk-v190-live-secret",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert "sk-v190-live-secret" not in serialized
    assert payload["raw_secret_returned"] is False
    assert payload["no_secret_echo"] is True


def test_production_safe_live_platform_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "production-live-platform-runtime",
            "--home",
            str(tmp_path),
            "--scenario",
            "provider-mcp-smoke",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).production_live_platform_runtime(
        scenario="provider-mcp-smoke",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["provider_connection_ready"] is True
    assert library_payload["mcp_connection_ready"] is True
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
