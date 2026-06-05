from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_live_cockpit_absorbs_workflow_bundle_review_operator_action() -> None:
    review = _bundle_review(endpoint_overrides={"web": "https://search.example.dev/query"})

    result = LiveCockpitRuntime().build(research_workflow_bundle_review=review)

    assert result.decision == "report"
    assert result.research_workflow_bundle_review is not None
    assert result.research_workflow_bundle_review_decision == "operator_input_required"
    assert result.research_workflow_bundle_review_endpoint_required_count == 1
    assert result.research_workflow_bundle_review_external_required_count == 0
    assert result.research_workflow_bundle_review_required_action_count == 1
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-bundle-review --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_workflow_bundle_review_is_blocked() -> None:
    review = _blocked_bundle_review()

    result = LiveCockpitRuntime().build(research_workflow_bundle_review=review)

    assert result.decision == "blocked"
    assert "research-workflow-bundle-review:live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_workflow_bundle_review() -> None:
    review = _bundle_review(endpoint_overrides={"web": "https://search.example.dev/query"})
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-bundle-review-json",
            review.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow_bundle_review=review.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_bundle_review_decision"] == "operator_input_required"
    assert payload["research_workflow_bundle_review_endpoint_required_count"] == 1
    assert payload["network_opened"] is False
    assert library_payload["research_workflow_bundle_review_required_action_count"] == 1


def _bundle_review(*, endpoint_overrides: dict[str, str]):
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave166.objective",
        endpoint_overrides=endpoint_overrides,
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave166",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    return LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave166",
    )


def _blocked_bundle_review():
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave166.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave166"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave166/blocked",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    return LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave166/blocked",
    )
