from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.platform_cockpit_runtime import PlatformCockpitRuntime


def test_platform_cockpit_reports_hermes_style_entry_surfaces_without_starting_them() -> None:
    result = PlatformCockpitRuntime().build()

    assert result.decision == "report"
    assert result.surface_count == 5
    assert result.selected_surface is None
    assert "zeus platform --surface api --json" in result.recommended_next_commands
    assert result.api_server_started is False
    assert result.acp_session_opened is False
    assert result.batch_executed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_platform_cockpit_inspects_api_surface_contract() -> None:
    result = PlatformCockpitRuntime().build(surface_id="api")

    assert result.decision == "report"
    assert result.selected_surface is not None
    assert result.selected_surface["surface_id"] == "api"
    assert "/health" in result.selected_surface["routes"]
    assert "/v1/chat/completions" in result.selected_surface["routes"]
    assert result.selected_surface["loopback_default"] is True
    assert result.selected_surface["non_loopback_requires_review"] is True
    assert result.api_server_started is False


def test_platform_cockpit_inspects_acp_and_batch_contracts() -> None:
    acp = PlatformCockpitRuntime().build(surface_id="acp")
    batch = PlatformCockpitRuntime().build(surface_id="batch")

    assert acp.selected_surface is not None
    assert acp.selected_surface["allowed_methods"] == ["initialize", "zeus.objective.compile"]
    assert acp.selected_surface["unknown_method_policy"] == "blocked"
    assert acp.acp_session_opened is False
    assert batch.selected_surface is not None
    assert batch.selected_surface["surface_id"] == "batch"
    assert batch.selected_surface["objective_execution"] == "compile_only"
    assert batch.batch_executed is False


def test_platform_cockpit_blocks_unknown_surface_inspection() -> None:
    result = PlatformCockpitRuntime().build(surface_id="unknown")

    assert result.decision == "blocked"
    assert result.selected_surface is None
    assert result.blocked_reasons == ("unknown_platform_surface",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_exposes_platform_cockpit_inspection() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "platform", "--surface", "api", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "report"
    assert payload["selected_surface"]["surface_id"] == "api"
    assert payload["api_server_started"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_platform_cockpit() -> None:
    payload = ZeusAgent().platform_status(surface_id="batch")

    assert payload["decision"] == "report"
    assert payload["selected_surface"]["surface_id"] == "batch"
    assert payload["batch_executed"] is False
