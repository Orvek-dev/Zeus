from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.platform_cockpit_runtime import PlatformCockpitRuntime
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v080_release_gate_reports_platform_surface_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v0.8.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.8.0"
    assert payload["release_stage"] == "platform_surface"
    assert payload["platform_surface_contract_available"] is True
    assert payload["cli_surface_contract_available"] is True
    assert payload["api_server_contract_available"] is True
    assert payload["gateway_surface_contract_available"] is True
    assert payload["acp_adapter_contract_available"] is True
    assert payload["batch_runner_contract_available"] is True
    assert payload["python_library_contract_available"] is True
    assert payload["platform_surface_ready"] is False
    assert "platform_surface_release_gate_manual_qa" in payload["required_checkpoint_evidence"]
    assert "platform_surface_gateway_manual_qa" in payload["required_checkpoint_evidence"]
    assert "platform_surface_secret_boundary_manual_qa" in payload["required_checkpoint_evidence"]
    assert "provider_loopback_manual_qa" not in payload["required_checkpoint_evidence"]
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["next_version"] == "v0.9.0"
    assert payload["no_secret_echo"] is True


def test_platform_cockpit_includes_gateway_entry_surface_without_delivery() -> None:
    result = PlatformCockpitRuntime().build(surface_id="gateway")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["selected_surface"]["surface_id"] == "gateway"
    assert payload["selected_surface"]["loopback_default"] is True
    assert payload["selected_surface"]["external_delivery_enabled"] is False
    assert payload["gateway_daemon_started"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_platform_surface_cli_reports_entrypoint_contracts() -> None:
    result = CliRunner().invoke(app, ["platform-surface", "--surface", "api", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.8.0"
    assert payload["surface_count"] >= 6
    assert payload["selected_surface"]["surface_id"] == "api"
    assert payload["api_server_contract_available"] is True
    assert payload["gateway_surface_contract_available"] is True
    assert payload["live_external_execution_enabled"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True


def test_platform_surface_cli_blocks_secret_like_surface_without_echo() -> None:
    raw_secret = "".join(("sk", "-", "v080-platform-secret"))
    result = CliRunner().invoke(app, ["platform-surface", "--surface", raw_secret, "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True).lower()
    assert payload["decision"] == "blocked"
    assert payload["selected_surface_id"] == "unknown"
    assert "unknown_platform_surface" in payload["blocked_reasons"]
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized
