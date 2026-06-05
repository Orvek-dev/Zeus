from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffRuntime,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorRuntime,
)
from tests.test_wave158_live_research_loopback_smoke import _plan
from tests.test_wave158_live_research_loopback_smoke import _SmokeServer
from tests.test_wave175_live_research_workflow_execution_handoff import _operator_action_chain
from tests.test_wave177_live_research_workflow_loopback_executor import _ready_handoff


def test_live_cockpit_reports_research_workflow_loopback_executor() -> None:
    executor = _executed_loopback()

    result = LiveCockpitRuntime().build(research_workflow_loopback_executor=executor)

    assert result.decision == "report"
    assert result.research_workflow_loopback_executor == executor
    assert result.research_workflow_loopback_executor_decision == "loopback_executed"
    assert result.research_workflow_loopback_executor_ready is True
    assert result.research_workflow_loopback_executor_result_count == 1
    assert result.research_workflow_loopback_executor_live_transport_enabled is True
    assert result.research_workflow_loopback_executor_non_loopback_network_opened is False
    assert result.network_opened is True
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-loopback-executor --json" in result.recommended_next_commands


def test_live_cockpit_blocks_blocked_research_workflow_loopback_executor() -> None:
    server = _SmokeServer()
    server.start()
    try:
        bundle = _operator_action_chain()
        handoff = LiveResearchWorkflowExecutionHandoffRuntime().build(
            preflight_plan=bundle["preflight_plan"],
            authorization=bundle["authorization"],
            executor_release=bundle["executor_release"],
            handoff_ref="research-execution-handoff://wave178/blocked",
        )
        plan = _plan(adapter_id="web", source_id="web", endpoint=f"{server.base_url}/web")
        executor = LiveResearchWorkflowLoopbackExecutorRuntime().execute(handoff=handoff, plan=plan)
    finally:
        server.shutdown()

    result = LiveCockpitRuntime().build(research_workflow_loopback_executor=executor)

    assert result.decision == "blocked"
    assert (
        "research-workflow-loopback-executor:"
        "research_workflow_loopback_executor_handoff_not_ready"
    ) in result.blocked_reasons
    assert result.network_opened is False
    assert result.research_workflow_loopback_executor_ready is False
    assert server.request_count == 0


def test_live_cockpit_loopback_executor_cli_and_library_surface_match() -> None:
    executor = _executed_loopback()
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live",
            "--research-workflow-loopback-executor-json",
            executor.model_dump_json(),
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
        research_workflow_loopback_executor=executor.to_payload(),
    )
    assert cli_payload == library_payload
    assert cli_payload["research_workflow_loopback_executor_decision"] == "loopback_executed"
    assert cli_payload["network_opened"] is True


def _executed_loopback():
    server = _SmokeServer()
    server.start()
    try:
        handoff = _ready_handoff("cockpit")
        plan = _plan(adapter_id="web", source_id="web", endpoint=f"{server.base_url}/web")
        return LiveResearchWorkflowLoopbackExecutorRuntime().execute(handoff=handoff, plan=plan)
    finally:
        server.shutdown()
