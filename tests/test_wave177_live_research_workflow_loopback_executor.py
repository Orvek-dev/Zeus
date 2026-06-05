from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffRuntime,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorRuntime,
)
from tests.test_wave158_live_research_loopback_smoke import _plan
from tests.test_wave158_live_research_loopback_smoke import _SmokeServer
from tests.test_wave175_live_research_workflow_execution_handoff import _operator_action_chain
from tests.test_wave175_live_research_workflow_execution_handoff import _ready_chain


def test_research_workflow_loopback_executor_runs_ready_handoff() -> None:
    server = _SmokeServer()
    server.start()
    try:
        handoff = _ready_handoff("ready")
        plan = _plan(adapter_id="web", source_id="web", endpoint=f"{server.base_url}/web")
        result = LiveResearchWorkflowLoopbackExecutorRuntime().execute(handoff=handoff, plan=plan)
    finally:
        server.shutdown()

    assert result.decision == "loopback_executed"
    assert result.handoff_manifest_id == handoff.manifest_id
    assert result.handoff_bound is True
    assert result.execution_plan_bound is True
    assert result.loopback_smoke_bound is True
    assert result.execution_allowed is True
    assert result.live_transport_enabled is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.result_count == 1
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True
    assert server.request_count == 1
    assert server.shutdown_complete is True


def test_research_workflow_loopback_executor_blocks_handoff_before_network() -> None:
    server = _SmokeServer()
    server.start()
    try:
        bundle = _operator_action_chain()
        handoff = LiveResearchWorkflowExecutionHandoffRuntime().build(
            preflight_plan=bundle["preflight_plan"],
            authorization=bundle["authorization"],
            executor_release=bundle["executor_release"],
            handoff_ref="research-execution-handoff://wave177/blocked",
        )
        plan = _plan(adapter_id="web", source_id="web", endpoint=f"{server.base_url}/web")
        result = LiveResearchWorkflowLoopbackExecutorRuntime().execute(handoff=handoff, plan=plan)
    finally:
        server.shutdown()

    assert result.decision == "blocked"
    assert "research_workflow_loopback_executor_handoff_not_ready" in result.blocked_reasons
    assert result.client_constructed is False
    assert result.research_invoked is False
    assert result.network_opened is False
    assert server.request_count == 0


def test_research_workflow_loopback_executor_blocks_non_loopback_plan() -> None:
    handoff = _ready_handoff("non-loopback")
    plan = _plan(
        adapter_id="web",
        source_id="web",
        endpoint="https://search.example.dev/query",
    )

    result = LiveResearchWorkflowLoopbackExecutorRuntime().execute(handoff=handoff, plan=plan)

    assert result.decision == "blocked"
    assert "research_workflow_loopback_executor_plan_not_loopback" in result.blocked_reasons
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.client_constructed is False


def test_research_workflow_loopback_executor_cli_and_library_surface_match() -> None:
    server = _SmokeServer()
    server.start()
    try:
        handoff = _ready_handoff("cli")
        plan = _plan(adapter_id="community", source_id="community", endpoint=f"{server.base_url}/community")
        env = {**os.environ, "PYTHONPATH": "src"}
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "zeus_agent",
                "live-research-workflow-loopback-executor",
                "--handoff-json",
                handoff.model_dump_json(),
                "--plan-json",
                plan.model_dump_json(),
                "--json",
            ],
            cwd=".",
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        library_payload = ZeusAgent().live_research_workflow_loopback_executor(
            handoff=handoff.to_payload(),
            plan=plan.to_payload(),
        )
    finally:
        server.shutdown()

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    assert _stable_payload(cli_payload) == _stable_payload(library_payload)
    assert cli_payload["decision"] == "loopback_executed"
    assert cli_payload["network_opened"] is True
    assert cli_payload["non_loopback_network_opened"] is False


def _ready_handoff(suffix: str):
    bundle = _ready_chain()
    return LiveResearchWorkflowExecutionHandoffRuntime().build(
        preflight_plan=bundle["preflight_plan"],
        authorization=bundle["authorization"],
        executor_release=bundle["executor_release"],
        handoff_ref="research-execution-handoff://wave177/{0}".format(suffix),
    )


def _stable_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "decision": payload["decision"],
        "adapter_id": payload["adapter_id"],
        "source_id": payload["source_id"],
        "result_count": payload["result_count"],
        "network_opened": payload["network_opened"],
        "non_loopback_network_opened": payload["non_loopback_network_opened"],
        "live_production_claimed": payload["live_production_claimed"],
    }
