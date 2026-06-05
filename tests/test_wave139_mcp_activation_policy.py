from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_mcp_activation_policy_runtime import LiveMcpActivationPolicyRuntime


def test_mcp_activation_policy_reports_inspection_only_without_starting_server() -> None:
    result = LiveMcpActivationPolicyRuntime().plan(
        server_id="mcp.github",
        startup_requested=False,
        resources_requested=False,
        prompts_requested=False,
        approval_ref=None,
    )

    assert result.decision == "policy_ready"
    assert result.server_known is True
    assert result.beta_enabled is True
    assert result.server_start_allowed is False
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_mcp_activation_policy_blocks_startup_without_approval_and_resource_prompts() -> None:
    result = LiveMcpActivationPolicyRuntime().plan(
        server_id="mcp.github",
        startup_requested=True,
        resources_requested=True,
        prompts_requested=True,
        approval_ref=None,
    )

    assert result.decision == "blocked"
    assert "mcp_server_start_requires_approval" in result.blocked_reasons
    assert "mcp_resources_require_separate_policy" in result.blocked_reasons
    assert "mcp_prompts_require_separate_policy" in result.blocked_reasons
    assert result.server_started is False


def test_mcp_activation_policy_plans_startup_with_approval_without_starting() -> None:
    result = LiveMcpActivationPolicyRuntime().plan(
        server_id="mcp.github",
        startup_requested=True,
        resources_requested=False,
        prompts_requested=False,
        approval_ref="approval://mcp.github/startup",
    )

    assert result.decision == "activation_planned"
    assert result.server_start_allowed is True
    assert result.approval_bound is True
    assert result.server_started is False
    assert result.network_opened is False


def test_cli_and_python_library_mcp_activation_policy() -> None:
    completed = CliRunner().invoke(
        app,
        [
            "live-mcp-activation-policy",
            "--server-id",
            "mcp.github",
            "--startup-requested",
            "--approval-ref",
            "approval://mcp.github/startup",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "activation_planned"
    assert payload["server_started"] is False

    library_payload = ZeusAgent().live_mcp_activation_policy(
        server_id="mcp.unknown",
        startup_requested=False,
    )
    assert library_payload["decision"] == "blocked"
    assert "unknown_mcp_server" in library_payload["blocked_reasons"]
