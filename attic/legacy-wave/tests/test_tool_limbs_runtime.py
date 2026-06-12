from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.tool_limbs_runtime import build_tool_limbs_contract


def test_tool_limbs_contract_exposes_native_mcp_api_limb_boundaries() -> None:
    result = build_tool_limbs_contract(tool_id="files.read")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.7.0"
    assert payload["objective_contract_id"] == "zeus.v0.7.0.tool_limbs"
    assert payload["selected_tool"]["tool_id"] == "files.read"
    assert payload["native_toolset_count"] >= 25
    assert payload["native_tool_count"] >= 80
    assert payload["native_tool_catalog_contract_available"] is True
    assert payload["mcp_tool_discovery_contract_available"] is True
    assert payload["api_connector_contract_available"] is True
    assert payload["include_exclude_policy_required"] is True
    assert payload["approval_lease_required"] is True
    assert payload["security_gate_required"] is True
    assert payload["live_external_execution_enabled"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_tool_limbs_blocks_secret_like_tool_id_without_echo() -> None:
    raw_secret = "".join(("sk", "-", "v070-tool-secret"))
    result = build_tool_limbs_contract(tool_id=raw_secret)
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert payload["selected_tool_id"] == "unknown"
    assert "unknown_tool" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized


def test_tool_limbs_cli_json_surface() -> None:
    result = CliRunner().invoke(
        app,
        ["tool-limbs", "--tool-id", "files.read", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "report"
    assert payload["selected_tool"]["tool_id"] == "files.read"
    assert payload["live_external_execution_enabled"] is False
    assert payload["no_secret_echo"] is True
