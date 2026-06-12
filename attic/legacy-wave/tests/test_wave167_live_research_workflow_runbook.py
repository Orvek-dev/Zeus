from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_live_research_runbook_turns_endpoint_gap_review_into_operator_step() -> None:
    review = _review(endpoint_overrides={"web": "https://search.example.dev/query"})

    result = LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave167/gaps",
    )

    assert result.decision == "runbook_ready"
    assert result.step_count == 1
    assert result.steps[0].state == "operator_action"
    assert "live-research-workflow" in result.steps[0].recommended_command
    assert "configure missing endpoints" in result.steps[0].operator_action
    assert result.steps[0].evidence_required is True
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_research_runbook_keeps_external_review_as_operator_step() -> None:
    review = _review(
        endpoint_overrides={
            "web": "https://search.example.dev/query",
            "community": "https://community.example.dev/search",
        },
    )

    result = LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave167/external",
    )

    assert result.decision == "runbook_ready"
    assert result.step_count == 1
    assert "production fetcher" in result.steps[0].operator_action
    assert "live-research-workflow-bundle-review" in result.steps[0].recommended_command
    assert result.credential_material_accessed is False


def test_live_research_runbook_blocks_blocked_review_without_echoing_secret() -> None:
    review = _blocked_review()

    result = LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave167/blocked",
    )
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert result.step_count == 1
    assert result.steps[0].state == "blocked"
    assert "ghp_" + "wave167" not in serialized
    assert result.no_secret_echo is True


def test_live_research_runbook_cli_and_library_surface_match() -> None:
    review = _review(endpoint_overrides={"web": "https://search.example.dev/query"})
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-runbook",
            "--review-json",
            review.model_dump_json(),
            "--runbook-ref",
            "runbook://wave167/cli",
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
    library_payload = ZeusAgent().live_research_workflow_runbook(
        review=review.to_payload(),
        runbook_ref="runbook://wave167/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "runbook_ready"


def _review(*, endpoint_overrides: dict[str, str]):
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave167.objective",
        endpoint_overrides=endpoint_overrides,
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave167",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    return LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave167",
    )


def _blocked_review():
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave167.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave167"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave167/blocked",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    return LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave167/blocked",
    )
