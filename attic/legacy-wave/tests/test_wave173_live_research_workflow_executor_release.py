from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationRuntime,
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


def test_research_workflow_executor_release_blocks_without_authorization() -> None:
    result = LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=None,
        release_ref="research-release://wave173/missing-auth",
        idempotency_key="wave173-missing-auth",
    )

    assert result.decision == "blocked"
    assert "research_workflow_authorization_required" in result.blocked_reasons
    assert result.executor_release_granted is False
    assert result.execution_allowed is False


def test_research_workflow_executor_release_grants_inert_release_without_transport() -> None:
    authorization = _ready_authorization()

    result = LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=authorization,
        release_ref="research-release://wave173/ready",
        idempotency_key="wave173-ready",
    )

    assert result.decision == "release_ready"
    assert result.release_envelope_ready is True
    assert result.executor_kind == "research"
    assert result.executor_release_granted is True
    assert result.execution_allowed is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_research_workflow_executor_release_blocks_not_ready_authorization() -> None:
    authorization = _operator_action_authorization()

    result = LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=authorization,
        release_ref="research-release://wave173/not-ready",
        idempotency_key="wave173-not-ready",
    )

    assert result.decision == "blocked"
    assert "research_workflow_authorization_not_ready" in result.blocked_reasons
    assert result.executor_release_granted is False
    assert result.execution_allowed is False


def test_research_workflow_executor_release_requires_release_ref_and_idempotency_key() -> None:
    authorization = _ready_authorization()

    result = LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=authorization,
        release_ref="",
        idempotency_key="",
    )

    assert result.decision == "blocked"
    assert "release_ref_required" in result.blocked_reasons
    assert "idempotency_key_required" in result.blocked_reasons
    assert result.execution_allowed is False


def test_research_workflow_executor_release_cli_and_library_surface_match() -> None:
    authorization = _ready_authorization()
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-executor-release",
            "--authorization-json",
            authorization.model_dump_json(),
            "--release-ref",
            "research-release://wave173/cli",
            "--idempotency-key",
            "wave173-cli",
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
    library_payload = ZeusAgent().live_research_workflow_executor_release(
        authorization=authorization.to_payload(),
        release_ref="research-release://wave173/cli",
        idempotency_key="wave173-cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "release_ready"
    assert cli_payload["executor_release_granted"] is True
    assert cli_payload["network_opened"] is False


def _ready_authorization():
    plan = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=_ready_runbook(),
        preflight_ref="research-preflight://wave173/ready",
    )
    return LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave173/ready",
        operator_approval_ref="operator-approval://wave173/ready",
        evidence_ref="evidence://wave173/ready",
    )


def _operator_action_authorization():
    plan = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=_operator_action_runbook(),
        preflight_ref="research-preflight://wave173/operator-action",
    )
    return LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave173/operator-action",
        operator_approval_ref="operator-approval://wave173/operator-action",
        evidence_ref="evidence://wave173/operator-action",
    )
