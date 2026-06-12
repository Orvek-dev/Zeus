from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanRuntime
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookResult
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookRuntime
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookStep
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_research_preflight_plan_requires_operator_action_before_candidate() -> None:
    runbook = _operator_action_runbook()

    result = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref="research-preflight://wave169/gaps",
    )

    assert result.decision == "operator_action_required"
    assert result.preflight_candidate_count == 0
    assert result.required_operator_action_count == 1
    assert "live_research_runbook_operator_action_required" in result.blocked_reasons
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_research_preflight_plan_blocks_blocked_runbook_without_echoing_secret() -> None:
    runbook = _blocked_runbook()

    result = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref="research-preflight://wave169/blocked",
    )
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert result.preflight_candidate_count == 0
    assert "ghp_" + "wave169" not in serialized
    assert result.no_secret_echo is True


def test_research_preflight_plan_creates_candidate_for_ready_runbook() -> None:
    runbook = _ready_runbook()

    result = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref="research-preflight://wave169/ready",
    )

    assert result.decision == "preflight_candidate_ready"
    assert result.preflight_candidate_count == 1
    assert result.required_operator_action_count == 0
    assert result.preflight_candidates[0].executor_kind == "research"
    assert result.preflight_candidates[0].operator_review_required is True
    assert result.preflight_candidates[0].evidence_required is True
    assert "live-research-loopback-smoke" in result.preflight_candidates[0].recommended_command
    assert result.network_opened is False


def test_research_preflight_plan_cli_and_library_surface_match() -> None:
    runbook = _operator_action_runbook()
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-preflight-plan",
            "--runbook-json",
            runbook.model_dump_json(),
            "--preflight-ref",
            "research-preflight://wave169/cli",
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
    library_payload = ZeusAgent().live_research_workflow_preflight_plan(
        runbook=runbook.to_payload(),
        preflight_ref="research-preflight://wave169/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "operator_action_required"


def _operator_action_runbook():
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave169.objective",
        endpoint_overrides={"web": "https://search.example.dev/query"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave169",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    review = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave169",
    )
    return LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave169",
    )


def _blocked_runbook():
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave169.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave169"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave169/blocked",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    review = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave169/blocked",
    )
    return LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave169/blocked",
    )


def _ready_runbook() -> LiveResearchWorkflowRunbookResult:
    step = LiveResearchWorkflowRunbookStep(
        step_id="research-runbook-step-ready",
        state="ready",
        operator_action="run controlled executor preflight",
        recommended_command="zeus live-research-loopback-smoke --plan-json <execution-plan-json> --json",
    )
    return LiveResearchWorkflowRunbookResult(
        decision="runbook_ready",
        runbook_id="live-research-workflow-runbook-wave169-ready",
        runbook_ref="runbook://wave169/ready",
        review_id="live-research-workflow-bundle-review-wave169-ready",
        review_ref="review://wave169/ready",
        objective_id="wave169.objective",
        review_decision="review_ready",
        step_count=1,
        steps=(step,),
    )
