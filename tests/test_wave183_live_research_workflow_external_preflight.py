from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightRuntime,
)
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave175_live_research_workflow_execution_handoff import _operator_action_chain
from tests.test_wave177_live_research_workflow_loopback_executor import _ready_handoff
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffRuntime,
)


def test_research_workflow_external_preflight_binds_ready_handoff_to_policy() -> None:
    handoff = _ready_handoff("external-preflight-ready")
    policy = _research_policy()

    result = LiveResearchWorkflowExternalPreflightRuntime().build(
        handoff=handoff,
        policy=policy,
        preflight_ref="research-workflow-external-preflight://wave183/ready",
        external_execution_ref="research-external://wave183/github",
        operator_approval_ref=policy.approval_ref or "",
        evidence_ref="evidence://wave183/ready",
    )

    assert result.decision == "external_preflight_ready"
    assert result.preflight_id is not None
    assert result.handoff_manifest_id == handoff.manifest_id
    assert result.policy_id == policy.policy_id
    assert result.source_id == "github"
    assert result.workflow_handoff_bound is True
    assert result.policy_bound is True
    assert result.approval_bound is True
    assert result.evidence_bound is True
    assert result.source_pin_bound is True
    assert result.external_transport_allowed is True
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_research_workflow_external_preflight_blocks_unapproved_policy_and_missing_evidence() -> None:
    handoff = _ready_handoff("external-preflight-blocked-policy")
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        source_pin_ref="source-pin://research/github",
    )

    result = LiveResearchWorkflowExternalPreflightRuntime().build(
        handoff=handoff,
        policy=policy,
        preflight_ref="research-workflow-external-preflight://wave183/policy-block",
        external_execution_ref="research-external://wave183/policy-block",
        operator_approval_ref="",
        evidence_ref="",
    )

    assert result.decision == "blocked"
    assert "research_workflow_external_policy_not_ready" in result.blocked_reasons
    assert "operator_approval_ref_required" in result.blocked_reasons
    assert "evidence_ref_required" in result.blocked_reasons
    assert result.external_transport_allowed is False
    assert result.network_opened is False


def test_research_workflow_external_preflight_blocks_blocked_handoff_and_secret_ref() -> None:
    bundle = _operator_action_chain()
    handoff = LiveResearchWorkflowExecutionHandoffRuntime().build(
        preflight_plan=bundle["preflight_plan"],
        authorization=bundle["authorization"],
        executor_release=bundle["executor_release"],
        handoff_ref="research-execution-handoff://wave183/blocked",
    )
    policy = _research_policy()
    raw_secret = "token=ghp_" + "wave183"

    result = LiveResearchWorkflowExternalPreflightRuntime().build(
        handoff=handoff,
        policy=policy,
        preflight_ref="research-workflow-external-preflight://wave183/blocked",
        external_execution_ref=f"research-external://wave183/secret?{raw_secret}",
        operator_approval_ref=policy.approval_ref or "",
        evidence_ref="evidence://wave183/blocked",
    )
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "research_workflow_external_handoff_not_ready" in result.blocked_reasons
    assert "secret_like_external_preflight_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert result.no_secret_echo is True


def test_research_workflow_external_preflight_cli_and_library_surface_match() -> None:
    handoff = _ready_handoff("external-preflight-cli")
    policy = _research_policy()
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-external-preflight",
            "--handoff-json",
            handoff.model_dump_json(),
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-ref",
            "research-workflow-external-preflight://wave183/cli",
            "--external-execution-ref",
            "research-external://wave183/cli",
            "--operator-approval-ref",
            policy.approval_ref or "",
            "--evidence-ref",
            "evidence://wave183/cli",
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
    library_payload = ZeusAgent().live_research_workflow_external_preflight(
        handoff=handoff.to_payload(),
        policy=policy.to_payload(),
        preflight_ref="research-workflow-external-preflight://wave183/cli",
        external_execution_ref="research-external://wave183/cli",
        operator_approval_ref=policy.approval_ref or "",
        evidence_ref="evidence://wave183/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "external_preflight_ready"
    assert cli_payload["network_opened"] is False
