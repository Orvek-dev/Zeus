from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.approval_cockpit_runtime import ApprovalCockpitRuntime


def test_approval_cockpit_reports_hitl_gates_without_granting_approval() -> None:
    result = ApprovalCockpitRuntime().build()

    assert result.decision == "report"
    assert result.approval_gate_count == 6
    assert result.required_gate_count == 6
    assert result.selected_gate is None
    assert "zeus approvals --approval-id provider-live --json" in result.recommended_next_commands
    assert result.approval_granted is False
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_approval_cockpit_explains_provider_live_risk() -> None:
    result = ApprovalCockpitRuntime().build(approval_id="provider-live")

    assert result.decision == "report"
    assert result.selected_gate is not None
    assert result.selected_gate["approval_id"] == "provider-live"
    assert result.selected_gate["risk_kind"] == "external_provider_network"
    assert result.selected_gate["human_prompt_required"] is True
    assert "model cost" in result.selected_gate["risk_summary"]
    assert result.approval_granted is False
    assert result.network_opened is False


def test_approval_cockpit_explains_destructive_and_delivery_risks() -> None:
    destructive = ApprovalCockpitRuntime().build(approval_id="destructive-action")
    delivery = ApprovalCockpitRuntime().build(approval_id="external-delivery")

    assert destructive.selected_gate is not None
    assert destructive.selected_gate["risk_kind"] == "destructive_local_action"
    assert destructive.selected_gate["approval_granted"] is False
    assert delivery.selected_gate is not None
    assert delivery.selected_gate["risk_kind"] == "external_delivery"
    assert delivery.selected_gate["target_allowlist_required"] is True
    assert delivery.approval_granted is False


def test_approval_cockpit_explains_mcp_live_risk() -> None:
    result = ApprovalCockpitRuntime().build(approval_id="mcp-live")

    assert result.decision == "report"
    assert result.selected_gate is not None
    assert result.selected_gate["approval_id"] == "mcp-live"
    assert result.selected_gate["risk_kind"] == "mcp_server_tool_surface"
    assert result.selected_gate["required_scope"] == "mcp.echo"
    assert result.approval_granted is False
    assert result.network_opened is False


def test_approval_cockpit_blocks_unknown_approval_gate() -> None:
    result = ApprovalCockpitRuntime().build(approval_id="unknown")

    assert result.decision == "blocked"
    assert result.selected_gate is None
    assert result.blocked_reasons == ("unknown_approval_gate",)
    assert result.approval_granted is False
    assert result.live_production_claimed is False


def test_cli_exposes_approval_cockpit() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "approvals", "--approval-id", "provider-live", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "report"
    assert payload["selected_gate"]["approval_id"] == "provider-live"
    assert payload["approval_granted"] is False


def test_python_library_exposes_approval_cockpit() -> None:
    payload = ZeusAgent().approval_status(approval_id="credential-access")

    assert payload["decision"] == "report"
    assert payload["selected_gate"]["approval_id"] == "credential-access"
    assert payload["selected_gate"]["risk_kind"] == "credential_material_access"
    assert payload["approval_granted"] is False
