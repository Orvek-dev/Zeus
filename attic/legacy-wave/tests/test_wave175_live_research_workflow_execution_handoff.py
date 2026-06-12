from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationRuntime,
)
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffRuntime,
)
from zeus_agent.live_research_workflow_executor_release_runtime import (
    LiveResearchWorkflowExecutorReleaseRuntime,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import (
    LiveResearchWorkflowPreflightPlanRuntime,
)
from tests.test_wave169_live_research_workflow_preflight_plan import (
    _operator_action_runbook,
    _ready_runbook,
)


def test_research_workflow_execution_handoff_binds_ready_chain_without_transport() -> None:
    bundle = _ready_chain()

    result = LiveResearchWorkflowExecutionHandoffRuntime().build(
        preflight_plan=bundle["preflight_plan"],
        authorization=bundle["authorization"],
        executor_release=bundle["executor_release"],
        handoff_ref="research-execution-handoff://wave175/ready",
    )

    assert result.decision == "handoff_ready"
    assert result.manifest_id is not None
    assert result.selected_candidate_id == bundle["authorization"].selected_candidate_id
    assert result.release_id == bundle["executor_release"].release_id
    assert result.executor_release_bound is True
    assert result.execution_allowed is True
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_research_workflow_execution_handoff_blocks_mismatched_authorization() -> None:
    bundle = _ready_chain()
    mismatched_authorization = bundle["authorization"].model_copy(
        update={"preflight_plan_id": "wrong-preflight-plan"}
    )

    result = LiveResearchWorkflowExecutionHandoffRuntime().build(
        preflight_plan=bundle["preflight_plan"],
        authorization=mismatched_authorization,
        executor_release=bundle["executor_release"],
        handoff_ref="research-execution-handoff://wave175/mismatch",
    )

    assert result.decision == "blocked"
    assert "research_workflow_handoff_authorization_preflight_mismatch" in result.blocked_reasons
    assert result.execution_allowed is False
    assert result.network_opened is False


def test_research_workflow_execution_handoff_blocks_not_ready_release() -> None:
    bundle = _operator_action_chain()

    result = LiveResearchWorkflowExecutionHandoffRuntime().build(
        preflight_plan=bundle["preflight_plan"],
        authorization=bundle["authorization"],
        executor_release=bundle["executor_release"],
        handoff_ref="research-execution-handoff://wave175/not-ready",
    )

    assert result.decision == "blocked"
    assert "research_workflow_handoff_preflight_not_ready" in result.blocked_reasons
    assert "research_workflow_handoff_authorization_not_ready" in result.blocked_reasons
    assert "research_workflow_handoff_executor_release_not_ready" in result.blocked_reasons
    assert result.execution_allowed is False


def test_research_workflow_execution_handoff_blocks_secret_note_and_production_request() -> None:
    bundle = _ready_chain()
    raw_secret = "sk-" + "wave175-secret"

    result = LiveResearchWorkflowExecutionHandoffRuntime().build(
        preflight_plan=bundle["preflight_plan"],
        authorization=bundle["authorization"],
        executor_release=bundle["executor_release"],
        handoff_ref="research-execution-handoff://wave175/secret",
        operator_note="operator note {0}".format(raw_secret),
        production_release_requested=True,
    )
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "production_release_forbidden" in result.blocked_reasons
    assert "secret_like_handoff_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True


def test_research_workflow_execution_handoff_cli_and_library_surface_match() -> None:
    bundle = _ready_chain()
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-execution-handoff",
            "--preflight-plan-json",
            bundle["preflight_plan"].model_dump_json(),
            "--authorization-json",
            bundle["authorization"].model_dump_json(),
            "--executor-release-json",
            bundle["executor_release"].model_dump_json(),
            "--handoff-ref",
            "research-execution-handoff://wave175/cli",
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
    library_payload = ZeusAgent().live_research_workflow_execution_handoff(
        preflight_plan=bundle["preflight_plan"].to_payload(),
        authorization=bundle["authorization"].to_payload(),
        executor_release=bundle["executor_release"].to_payload(),
        handoff_ref="research-execution-handoff://wave175/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "handoff_ready"
    assert cli_payload["network_opened"] is False
    assert cli_payload["live_transport_enabled"] is False


def _ready_chain():
    return _chain(_ready_runbook(), suffix="ready")


def _operator_action_chain():
    return _chain(_operator_action_runbook(), suffix="operator-action")


def _chain(runbook, suffix: str):
    preflight_plan = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref="research-preflight://wave175/{0}".format(suffix),
    )
    authorization = LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=preflight_plan,
        authorization_ref="research-authorization://wave175/{0}".format(suffix),
        operator_approval_ref="operator-approval://wave175/{0}".format(suffix),
        evidence_ref="evidence://wave175/{0}".format(suffix),
    )
    executor_release = LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=authorization,
        release_ref="research-release://wave175/{0}".format(suffix),
        idempotency_key="wave175-{0}".format(suffix),
    )
    return {
        "preflight_plan": preflight_plan,
        "authorization": authorization,
        "executor_release": executor_release,
    }
