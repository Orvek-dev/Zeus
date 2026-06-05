from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.mcp_live_server_runtime import build_mcp_live_server_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v100rc3_release_gate_reports_mcp_live_server_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.3")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.3"
    assert payload["release_stage"] == "mcp_live_server"
    assert payload["mcp_live_server_contract_available"] is True
    assert payload["mcp_catalog_available"] is True
    assert payload["mcp_activation_policy_available"] is True
    assert payload["mcp_request_envelope_available"] is True
    assert payload["mcp_loopback_http_available"] is True
    assert payload["mcp_remote_server_available"] is False
    assert payload["mcp_live_server_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] is None
    assert "mcp_live_server_loopback_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_mcp_live_server_status_reports_contract_without_side_effects() -> None:
    result = build_mcp_live_server_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.3"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.3.mcp_live_server"
    assert payload["scenario"] == "status"
    assert payload["mcp_remote_server_available"] is False
    assert payload["mcp_resources_enabled"] is False
    assert payload["mcp_prompts_enabled"] is False
    assert payload["mcp_live_server_ready"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["handler_executed"] is False
    assert payload["mcp_surface_scan"]["unsafe_marker_count"] == 0
    assert payload["no_secret_echo"] is True


def test_mcp_live_server_loopback_smoke_executes_with_audit_and_cleanup(monkeypatch) -> None:
    material = "mcp-" + "rc3-token-value"
    monkeypatch.setenv("ZEUS_RC3_MCP_TOKEN", material)

    result = build_mcp_live_server_contract(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC3_MCP_TOKEN",
        query="Zeus MCP live server checkpoint",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "report"
    assert payload["mcp_live_server_ready"] is True
    assert payload["production_ready"] is False
    assert payload["mcp_remote_server_available"] is False
    assert payload["mcp_smoke"]["activation_policy"]["decision"] == "activation_planned"
    assert payload["mcp_smoke"]["activation_policy"]["server_started"] is False
    assert payload["mcp_smoke"]["execution"]["decision"] == "executed"
    assert payload["mcp_smoke"]["execution"]["local_http_loopback"] is True
    assert payload["mcp_smoke"]["execution"]["non_loopback_network_opened"] is False
    assert payload["mcp_smoke"]["audit"]["decision"] == "audit_ready"
    assert payload["mcp_smoke"]["redaction"]["decision"] == "redacted"
    assert payload["mcp_smoke"]["server_shutdown_complete"] is True
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["credential_material_accessed"] is True
    assert payload["live_production_claimed"] is False
    assert payload["mcp_surface_scan"]["unsafe_marker_count"] == 0
    assert payload["no_secret_echo"] is True
    assert material not in serialized


def test_mcp_live_server_blocks_missing_secret_before_loopback_network() -> None:
    result = build_mcp_live_server_contract(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC3_MISSING_MCP_TOKEN",
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "secret_material_missing" in payload["blocked_reasons"]
    assert payload["mcp_live_server_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True


def test_mcp_live_server_blocks_prompt_injection_scan_without_network() -> None:
    result = build_mcp_live_server_contract(scenario="prompt-injection-scan")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "mcp_prompt_injection_detected" in payload["blocked_reasons"]
    assert payload["mcp_surface_scan"]["unsafe_marker_count"] == 1
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True


def test_mcp_live_server_cli_and_library_match(monkeypatch) -> None:
    material = "mcp-" + "rc3-token-value"
    monkeypatch.setenv("ZEUS_RC3_MCP_TOKEN", material)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "mcp-live-server",
            "--scenario",
            "loopback-smoke",
            "--secret-ref",
            "env://ZEUS_RC3_MCP_TOKEN",
            "--json",
        ],
    )
    library_payload = ZeusAgent().mcp_live_server(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC3_MCP_TOKEN",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["mcp_live_server_ready"] is True
    assert library_payload["mcp_live_server_ready"] is True
    assert cli_payload["mcp_remote_server_available"] is False
    assert material not in completed.stdout
    assert material not in json.dumps(library_payload)
