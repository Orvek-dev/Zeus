from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanRuntime
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_live_cockpit_absorbs_research_preflight_plan_operator_action() -> None:
    plan = _preflight_plan(endpoint_overrides={"web": "https://search.example.dev/query"})

    result = LiveCockpitRuntime().build(research_workflow_preflight_plan=plan)

    assert result.decision == "report"
    assert result.research_workflow_preflight_plan is not None
    assert result.research_workflow_preflight_plan_decision == "operator_action_required"
    assert result.research_workflow_preflight_candidate_count == 0
    assert result.research_workflow_preflight_required_operator_action_count == 1
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-preflight-plan --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_research_preflight_plan_is_blocked() -> None:
    plan = _blocked_preflight_plan()

    result = LiveCockpitRuntime().build(research_workflow_preflight_plan=plan)

    assert result.decision == "blocked"
    assert "research-workflow-preflight-plan:live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_research_preflight_plan() -> None:
    plan = _preflight_plan(endpoint_overrides={"web": "https://search.example.dev/query"})
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-preflight-plan-json",
            plan.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow_preflight_plan=plan.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_preflight_plan_decision"] == "operator_action_required"
    assert payload["research_workflow_preflight_required_operator_action_count"] == 1
    assert payload["network_opened"] is False
    assert library_payload["research_workflow_preflight_candidate_count"] == 0


def _preflight_plan(*, endpoint_overrides: dict[str, str]):
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave170.objective",
        endpoint_overrides=endpoint_overrides,
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave170",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    review = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave170",
    )
    runbook = LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave170",
    )
    return LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref="research-preflight://wave170",
    )


def _blocked_preflight_plan():
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave170.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave170"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave170/blocked",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    review = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave170/blocked",
    )
    runbook = LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave170/blocked",
    )
    return LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref="research-preflight://wave170/blocked",
    )
