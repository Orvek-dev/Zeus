from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusRuntime,
)
from tests.test_wave178_live_cockpit_research_workflow_loopback_executor import _executed_loopback
from tests.test_wave180_live_research_workflow_execution_registry import _status


def test_live_cockpit_reports_research_workflow_execution_status() -> None:
    status = _status()

    result = LiveCockpitRuntime().build(research_workflow_execution_status=status)

    assert result.decision == "report"
    assert result.research_workflow_execution_status == status
    assert result.research_workflow_execution_status_decision == "execution_recorded"
    assert result.research_workflow_execution_status_ready is True
    assert result.research_workflow_execution_status_status_id == status.status_id
    assert result.research_workflow_execution_status_evidence_bound is True
    assert result.research_workflow_execution_status_loopback_network_seen is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-execution-status --json" in result.recommended_next_commands


def test_live_cockpit_blocks_blocked_research_workflow_execution_status() -> None:
    blocked = LiveResearchWorkflowExecutionStatusRuntime().build(
        loopback_executor=_executed_loopback(),
        status_ref="research-workflow-execution-status://wave181/blocked",
        evidence_ref="",
    )

    result = LiveCockpitRuntime().build(research_workflow_execution_status=blocked)

    assert result.decision == "blocked"
    assert (
        "research-workflow-execution-status:evidence_ref_required"
    ) in result.blocked_reasons
    assert result.research_workflow_execution_status_ready is False
    assert result.network_opened is False


def test_live_cockpit_execution_status_cli_and_library_surface_match() -> None:
    status = _status()
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live",
            "--research-workflow-execution-status-json",
            status.model_dump_json(),
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    library_payload = ZeusAgent().live_status(
        research_workflow_execution_status=status.to_payload(),
    )
    assert cli_payload == library_payload
    assert cli_payload["research_workflow_execution_status_decision"] == "execution_recorded"
    assert cli_payload["network_opened"] is False
