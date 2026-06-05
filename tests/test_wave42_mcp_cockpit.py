from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.mcp_cockpit_runtime import McpCockpitRuntime


def test_mcp_cockpit_reports_catalog_without_starting_servers() -> None:
    # Given: the user asks for the MCP cockpit overview.
    result = McpCockpitRuntime().build()

    # Then: Zeus exposes catalog breadth while keeping MCP live execution closed.
    assert result.decision == "report"
    assert result.catalog_entry_count == 25
    assert result.beta_enabled_count == 10
    assert result.selected_server is None
    assert "zeus mcp --server-id mcp.github --json" in result.recommended_next_commands
    assert result.resources_prompts_wrappers_enabled is False
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.live_production_claimed is False


def test_mcp_cockpit_inspects_known_beta_server() -> None:
    # Given: the user inspects a known beta MCP catalog server.
    result = McpCockpitRuntime().build(server_id="mcp.github")

    # Then: Zeus returns the pinned server contract without launching it.
    assert result.decision == "report"
    assert result.selected_server is not None
    assert result.selected_server["server_id"] == "mcp.github"
    assert result.selected_server["display_name"] == "GitHub"
    assert result.selected_server["beta_enabled"] is True
    assert result.selected_server["include_tool_count"] == 3
    assert result.network_opened is False
    assert result.handler_executed is False


def test_mcp_cockpit_blocks_unknown_server_inspection() -> None:
    # Given: the user asks to inspect an unknown MCP server id.
    result = McpCockpitRuntime().build(server_id="mcp.unknown")

    # Then: the cockpit fails closed instead of fabricating server state.
    assert result.decision == "blocked"
    assert result.selected_server is None
    assert result.blocked_reasons == ("unknown_mcp_server",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_exposes_mcp_cockpit_inspection() -> None:
    # Given: the user opens MCP cockpit inspection from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "mcp", "--server-id", "mcp.github", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes the known server without side effects.
    assert payload["decision"] == "report"
    assert payload["selected_server"]["server_id"] == "mcp.github"
    assert payload["selected_server"]["include_tool_count"] == 3
    assert payload["network_opened"] is False


def test_python_library_exposes_mcp_cockpit() -> None:
    # Given: a Python user wants MCP catalog status.
    payload = ZeusAgent().mcp_status(server_id="mcp.github")

    # Then: the library returns the same JSON-compatible inspection.
    assert payload["decision"] == "report"
    assert payload["selected_server"]["display_name"] == "GitHub"
    assert payload["live_production_claimed"] is False
