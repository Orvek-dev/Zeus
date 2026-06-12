from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportRuntime
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionRuntime,
)
from tests.test_wave141_live_research_external_transport import _client_result
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave185_live_research_workflow_external_execution import _preflight


def test_live_cockpit_reports_research_workflow_external_execution() -> None:
    execution = _ready_external_execution()

    result = LiveCockpitRuntime().build(research_workflow_external_execution=execution)

    assert result.decision == "report"
    assert result.research_workflow_external_execution == execution
    assert result.research_workflow_external_execution_decision == "external_execution_recorded"
    assert result.research_workflow_external_execution_ready is True
    assert result.research_workflow_external_execution_id == execution.execution_id
    assert result.research_workflow_external_transport_execution_id == execution.external_transport_execution_id
    assert result.research_workflow_external_execution_network_seen is True
    assert result.research_workflow_external_execution_non_loopback_network_seen is True
    assert result.research_workflow_external_execution_live_transport_enabled is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-external-execution --json" in result.recommended_next_commands


def test_live_cockpit_blocks_blocked_research_workflow_external_execution() -> None:
    policy = _research_policy()
    preflight = _preflight("cockpit-blocked", policy=policy)
    blocked = LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        execution_record_ref="research-workflow-external-execution://wave186/blocked",
    )

    result = LiveCockpitRuntime().build(research_workflow_external_execution=blocked)

    assert result.decision == "blocked"
    assert (
        "research-workflow-external-execution:"
        "research_external_transport_result_required"
    ) in result.blocked_reasons
    assert result.research_workflow_external_execution_ready is False
    assert result.network_opened is False


def test_live_cockpit_external_execution_cli_and_library_surface_match() -> None:
    execution = _ready_external_execution()
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live",
            "--research-workflow-external-execution-json",
            execution.model_dump_json(),
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
        research_workflow_external_execution=execution.to_payload(),
    )
    assert cli_payload == library_payload
    assert cli_payload["research_workflow_external_execution_decision"] == "external_execution_recorded"
    assert cli_payload["research_workflow_external_execution_network_seen"] is True
    assert cli_payload["network_opened"] is False


def _ready_external_execution():
    policy = _research_policy()
    preflight = _preflight("cockpit-ready", policy=policy)
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=policy,
        client_result=_client_result(),
        execution_ref=preflight.external_execution_ref or "",
    )
    return LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        external_result=external_result,
        execution_record_ref="research-workflow-external-execution://wave186/ready",
    )
