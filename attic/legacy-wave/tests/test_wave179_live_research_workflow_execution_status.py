from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusRuntime,
)
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffRuntime,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorRuntime,
)
from tests.test_wave158_live_research_loopback_smoke import _plan
from tests.test_wave158_live_research_loopback_smoke import _SmokeServer
from tests.test_wave175_live_research_workflow_execution_handoff import _operator_action_chain
from tests.test_wave178_live_cockpit_research_workflow_loopback_executor import _executed_loopback


def test_research_workflow_execution_status_records_loopback_executor() -> None:
    executor = _executed_loopback()

    result = LiveResearchWorkflowExecutionStatusRuntime().build(
        loopback_executor=executor,
        status_ref="research-workflow-execution-status://wave179/recorded",
        evidence_ref="evidence://wave179/recorded",
    )

    assert result.decision == "execution_recorded"
    assert result.status_id is not None
    assert result.workflow_execution_id == executor.workflow_execution_id
    assert result.loopback_executor_bound is True
    assert result.evidence_bound is True
    assert result.loopback_network_seen is True
    assert result.non_loopback_network_opened is False
    assert result.production_ready is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_research_workflow_execution_status_blocks_missing_evidence_and_blocked_executor() -> None:
    blocked_executor = _blocked_executor()

    result = LiveResearchWorkflowExecutionStatusRuntime().build(
        loopback_executor=blocked_executor,
        status_ref="research-workflow-execution-status://wave179/blocked",
        evidence_ref="",
    )

    assert result.decision == "blocked"
    assert "evidence_ref_required" in result.blocked_reasons
    assert "research_workflow_loopback_executor_not_executed" in result.blocked_reasons
    assert result.loopback_executor_bound is False
    assert result.network_opened is False


def test_research_workflow_execution_status_cli_and_library_surface_match() -> None:
    executor = _executed_loopback()
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-execution-status",
            "--loopback-executor-json",
            executor.model_dump_json(),
            "--status-ref",
            "research-workflow-execution-status://wave179/cli",
            "--evidence-ref",
            "evidence://wave179/cli",
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
    library_payload = ZeusAgent().live_research_workflow_execution_status(
        loopback_executor=executor.to_payload(),
        status_ref="research-workflow-execution-status://wave179/cli",
        evidence_ref="evidence://wave179/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "execution_recorded"
    assert cli_payload["network_opened"] is False


def _blocked_executor():
    server = _SmokeServer()
    server.start()
    try:
        bundle = _operator_action_chain()
        handoff = LiveResearchWorkflowExecutionHandoffRuntime().build(
            preflight_plan=bundle["preflight_plan"],
            authorization=bundle["authorization"],
            executor_release=bundle["executor_release"],
            handoff_ref="research-execution-handoff://wave179/blocked",
        )
        plan = _plan(adapter_id="web", source_id="web", endpoint=f"{server.base_url}/web")
        return LiveResearchWorkflowLoopbackExecutorRuntime().execute(handoff=handoff, plan=plan)
    finally:
        server.shutdown()
