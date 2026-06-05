from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.mcp_owned_client_live_runtime import build_mcp_owned_client_live_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v100rc9_release_gate_reports_mcp_owned_client_live_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.9")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.9"
    assert payload["release_stage"] == "mcp_owned_client_live"
    assert payload["mcp_owned_client_live_contract_available"] is True
    assert payload["mcp_owned_client_transport_available"] is True
    assert payload["mcp_owned_client_adapter_available"] is True
    assert payload["mcp_owned_client_live_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] is None
    assert "mcp_owned_client_live_smoke_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_mcp_owned_client_live_status_reports_without_side_effects() -> None:
    result = build_mcp_owned_client_live_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.9"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.9.mcp_owned_client_live"
    assert payload["scenario"] == "status"
    assert payload["mcp_owned_client_live_ready"] is False
    assert payload["operator_live_opted_in"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["server_started"] is False
    assert payload["resources_enabled"] is False
    assert payload["prompts_enabled"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_mcp_owned_client_live_blocks_missing_operator_optin_before_secret_or_network() -> None:
    result = build_mcp_owned_client_live_contract(scenario="blocked-missing-opt-in")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "operator_live_opt_in_required" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is False
    assert payload["secret_material_available"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["tool_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_mcp_owned_client_live_blocks_missing_secret_before_owned_client(monkeypatch) -> None:
    monkeypatch.delenv("ZEUS_RC9_MCP_TOKEN", raising=False)

    result = build_mcp_owned_client_live_contract(scenario="blocked-missing-secret")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "secret_material_missing" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is True
    assert payload["endpoint_allowlisted"] is True
    assert payload["credential_material_accessed"] is True
    assert payload["network_opened"] is False
    assert payload["tool_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_mcp_owned_client_live_smoke_binds_mcp_client_audit_and_redaction(monkeypatch) -> None:
    material = "mcp-" + "rc9-material-value"
    monkeypatch.setenv("ZEUS_RC9_MCP_TOKEN", material)

    result = build_mcp_owned_client_live_contract(scenario="owned-client-smoke")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "report"
    assert payload["mcp_owned_client_live_ready"] is True
    assert payload["operator_live_opted_in"] is True
    assert payload["endpoint_allowlisted"] is True
    assert payload["secret_material_available"] is True
    assert payload["mcp_owned_client_smoke"]["policy"]["decision"] == "policy_ready"
    assert payload["mcp_owned_client_smoke"]["preflight"]["decision"] == "preflight_ready"
    assert payload["mcp_owned_client_smoke"]["mcp_owned_client_transport"]["decision"] == "executed"
    assert payload["mcp_owned_client_smoke"]["audit"]["decision"] == "audit_ready"
    assert payload["mcp_owned_client_smoke"]["redaction"]["decision"] == "redacted"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is True
    assert payload["controlled_external_side_effects"] is True
    assert payload["credential_material_accessed"] is True
    assert payload["material_released"] is False
    assert payload["server_started"] is False
    assert payload["resources_enabled"] is False
    assert payload["prompts_enabled"] is False
    assert payload["live_production_claimed"] is False
    assert payload["production_ready"] is False
    assert material not in serialized
    assert payload["no_secret_echo"] is True


def test_mcp_owned_client_live_cli_and_library_match(monkeypatch) -> None:
    material = "mcp-" + "rc9-material-value"
    monkeypatch.setenv("ZEUS_RC9_MCP_TOKEN", material)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "mcp-owned-client-live",
            "--scenario",
            "owned-client-smoke",
            "--json",
        ],
    )
    library_payload = ZeusAgent().mcp_owned_client_live(scenario="owned-client-smoke")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["mcp_owned_client_live_ready"] is True
    assert library_payload["mcp_owned_client_live_ready"] is True
    assert material not in completed.stdout
    assert material not in json.dumps(library_payload)
