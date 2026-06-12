from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime


def test_live_cockpit_exposes_activation_pipeline_without_execution_permission() -> None:
    result = LiveCockpitRuntime().build()

    assert result.activation_pipeline_count == 5
    stage_ids = [stage["stage_id"] for stage in result.activation_pipeline]
    assert stage_ids == [
        "live_profile",
        "approval_receipt",
        "live_preflight",
        "live_handoff",
        "live_execute_plan",
    ]
    assert all(stage["execution_allowed"] is False for stage in result.activation_pipeline)
    assert all(stage["network_opened"] is False for stage in result.activation_pipeline)
    assert result.live_production_claimed is False


def test_live_cockpit_recommends_new_activation_pipeline_commands() -> None:
    result = LiveCockpitRuntime().build()

    assert "zeus live-profile --json" in result.recommended_next_commands
    assert "zeus approval-receipt --json" in result.recommended_next_commands
    assert "zeus live-preflight --json" in result.recommended_next_commands
    assert "zeus live-handoff --json" in result.recommended_next_commands
    assert "zeus live-execute-plan --json" in result.recommended_next_commands


def test_cli_exposes_live_activation_pipeline() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "live", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["activation_pipeline_count"] == 5
    assert payload["activation_pipeline"][0]["stage_id"] == "live_profile"
    assert payload["activation_pipeline"][-1]["stage_id"] == "live_execute_plan"
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_live_activation_pipeline() -> None:
    payload = ZeusAgent().live_status()

    assert payload["activation_pipeline_count"] == 5
    assert payload["activation_pipeline"][2]["stage_id"] == "live_preflight"
    assert payload["activation_pipeline"][3]["execution_allowed"] is False
