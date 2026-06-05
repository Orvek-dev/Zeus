from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationRuntime,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import (
    LiveResearchWorkflowPreflightPlanRuntime,
)
from tests.test_wave169_live_research_workflow_preflight_plan import (
    _blocked_runbook,
    _operator_action_runbook,
    _ready_runbook,
)


def test_research_workflow_authorization_requires_ready_preflight_plan() -> None:
    plan = _preflight_plan(_operator_action_runbook(), "research-preflight://wave171/gaps")

    result = LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave171/gaps",
        operator_approval_ref="operator-approval://wave171/gaps",
        evidence_ref="evidence://wave171/gaps",
    )

    assert result.decision == "operator_action_required"
    assert result.authorization_envelope_ready is False
    assert result.authorized_candidate_count == 0
    assert "live_research_preflight_plan_operator_action_required" in result.blocked_reasons
    assert result.execution_allowed is False
    assert result.network_opened is False


def test_research_workflow_authorization_blocks_bad_preflight_without_secret_echo() -> None:
    plan = _preflight_plan(_blocked_runbook(), "research-preflight://wave171/blocked")

    result = LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave171/blocked",
        operator_approval_ref="operator-approval://wave171/blocked",
        evidence_ref="evidence://wave171/blocked",
    )
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_preflight_plan_blocked" in result.blocked_reasons
    assert "live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert "ghp_" + "wave169" not in serialized
    assert result.no_secret_echo is True


def test_research_workflow_authorization_binds_ready_candidate_without_execution() -> None:
    plan = _preflight_plan(_ready_runbook(), "research-preflight://wave171/ready")

    result = LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave171/ready",
        operator_approval_ref="operator-approval://wave171/ready",
        evidence_ref="evidence://wave171/ready",
    )

    assert result.decision == "authorization_ready"
    assert result.authorization_envelope_ready is True
    assert result.operator_approval_bound is True
    assert result.evidence_bound is True
    assert result.authorized_candidate_count == 1
    assert result.selected_candidate_id == plan.preflight_candidates[0].candidate_id
    assert result.executor_release_granted is False
    assert result.execution_allowed is False
    assert result.live_production_claimed is False


def test_research_workflow_authorization_requires_approval_and_evidence_refs() -> None:
    plan = _preflight_plan(_ready_runbook(), "research-preflight://wave171/missing-refs")

    result = LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave171/missing-refs",
        operator_approval_ref="",
        evidence_ref="",
    )

    assert result.decision == "operator_action_required"
    assert "operator_approval_ref_required" in result.blocked_reasons
    assert "evidence_ref_required" in result.blocked_reasons
    assert result.authorization_envelope_ready is False
    assert result.execution_allowed is False


def test_research_workflow_authorization_cli_and_library_surface_match() -> None:
    plan = _preflight_plan(_ready_runbook(), "research-preflight://wave171/cli")
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-authorization",
            "--preflight-plan-json",
            plan.model_dump_json(),
            "--authorization-ref",
            "research-authorization://wave171/cli",
            "--operator-approval-ref",
            "operator-approval://wave171/cli",
            "--evidence-ref",
            "evidence://wave171/cli",
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
    library_payload = ZeusAgent().live_research_workflow_authorization(
        preflight_plan=plan.to_payload(),
        authorization_ref="research-authorization://wave171/cli",
        operator_approval_ref="operator-approval://wave171/cli",
        evidence_ref="evidence://wave171/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "authorization_ready"
    assert cli_payload["execution_allowed"] is False


def _preflight_plan(runbook, preflight_ref: str):
    return LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref=preflight_ref,
    )
