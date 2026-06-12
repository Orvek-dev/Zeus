from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.tool_cockpit_runtime import ToolCockpitRuntime


def test_tool_cockpit_reports_catalog_without_dispatch() -> None:
    # Given: the user asks for a Hermes-style native tool cockpit overview.
    result = ToolCockpitRuntime().build()

    # Then: Zeus exposes tool breadth while keeping execution closed.
    assert result.decision == "report"
    assert result.toolset_count == 25
    assert result.tool_count == 80
    assert result.selected_tool is None
    assert "zeus tools --tool-id files.read --json" in result.recommended_next_commands
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.live_production_claimed is False


def test_tool_cockpit_inspects_known_tool() -> None:
    # Given: the user inspects a known native tool id.
    result = ToolCockpitRuntime().build(tool_id="files.read")

    # Then: Zeus returns the pinned local tool contract without dispatching it.
    assert result.decision == "report"
    assert result.selected_tool is not None
    assert result.selected_tool["tool_id"] == "files.read"
    assert result.selected_tool["toolset_id"] == "native.files"
    assert result.selected_tool["capability_id"] == "api.tool.files.read"
    assert result.selected_tool["source"] == "local"
    assert result.selected_tool["network_opened"] is False
    assert result.handler_executed is False


def test_tool_cockpit_blocks_unknown_tool_inspection() -> None:
    # Given: the user asks to inspect an unknown tool id.
    result = ToolCockpitRuntime().build(tool_id="files.missing")

    # Then: the cockpit fails closed instead of fabricating capability state.
    assert result.decision == "blocked"
    assert result.selected_tool is None
    assert result.blocked_reasons == ("unknown_tool",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_exposes_tool_cockpit_inspection() -> None:
    # Given: the user opens native tool cockpit inspection from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "tools", "--tool-id", "files.read", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes the known tool without side effects.
    assert payload["decision"] == "report"
    assert payload["selected_tool"]["tool_id"] == "files.read"
    assert payload["selected_tool"]["toolset_id"] == "native.files"
    assert payload["network_opened"] is False


def test_python_library_exposes_tool_cockpit() -> None:
    # Given: a Python user wants native tool catalog status.
    payload = ZeusAgent().tool_status(tool_id="files.read")

    # Then: the library returns the same JSON-compatible inspection.
    assert payload["decision"] == "report"
    assert payload["selected_tool"]["capability_id"] == "api.tool.files.read"
    assert payload["live_production_claimed"] is False
