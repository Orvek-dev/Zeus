from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.workflow_cockpit_runtime import WorkflowCockpitRuntime


def test_workflow_cockpit_reports_goal_workflows_without_execution() -> None:
    # Given: the user asks for Zeus workflow cockpit status.
    result = WorkflowCockpitRuntime().build()

    # Then: Zeus exposes goal-loop workflow breadth without starting automation.
    assert result.decision == "report"
    assert result.workflow_count == 3
    assert result.planned_workflow_count == 3
    assert result.blocked_workflow_count == 0
    assert result.selected_workflow is None
    assert "zeus workflow --workflow-id adaptive --json" in result.recommended_next_commands
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_workflow_cockpit_inspects_adaptive_workflow() -> None:
    # Given: the user inspects the adaptive workflow compiler surface.
    result = WorkflowCockpitRuntime().build(workflow_id="adaptive")

    # Then: Zeus shows fan-out planning while preserving authority boundaries.
    assert result.decision == "report"
    assert result.selected_workflow is not None
    assert result.selected_workflow["workflow_id"] == "adaptive"
    assert result.selected_workflow["decision"] == "compiled"
    assert result.selected_workflow["selected_pattern"] == "fan_out_and_synthesize"
    assert result.selected_workflow["authority_widened"] is False
    assert result.selected_workflow["network_opened"] is False


def test_workflow_cockpit_inspects_standing_order() -> None:
    # Given: the user inspects standing order planning.
    result = WorkflowCockpitRuntime().build(workflow_id="standing-order")

    # Then: Zeus keeps cron disabled and recurrence guarded by default.
    assert result.decision == "report"
    assert result.selected_workflow is not None
    assert result.selected_workflow["workflow_id"] == "standing-order"
    assert result.selected_workflow["decision"] == "planned"
    assert result.selected_workflow["cron_enabled"] is False
    assert result.selected_workflow["recurrence_guard_enabled"] is True
    assert result.selected_workflow["external_delivery_opened"] is False


def test_workflow_cockpit_blocks_unknown_workflow_inspection() -> None:
    # Given: the user asks to inspect an unknown workflow id.
    result = WorkflowCockpitRuntime().build(workflow_id="unknown")

    # Then: the cockpit fails closed instead of fabricating workflow state.
    assert result.decision == "blocked"
    assert result.selected_workflow is None
    assert result.blocked_reasons == ("unknown_workflow",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_exposes_workflow_cockpit_inspection() -> None:
    # Given: the user opens workflow cockpit inspection from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "workflow", "--workflow-id", "adaptive", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes adaptive planning without side effects.
    assert payload["decision"] == "report"
    assert payload["selected_workflow"]["workflow_id"] == "adaptive"
    assert payload["selected_workflow"]["selected_pattern"] == "fan_out_and_synthesize"
    assert payload["network_opened"] is False


def test_python_library_exposes_workflow_cockpit() -> None:
    # Given: a Python user wants workflow status.
    payload = ZeusAgent().workflow_status(workflow_id="standing-order")

    # Then: the library returns the same JSON-compatible inspection.
    assert payload["decision"] == "report"
    assert payload["selected_workflow"]["workflow_id"] == "standing-order"
    assert payload["live_production_claimed"] is False
