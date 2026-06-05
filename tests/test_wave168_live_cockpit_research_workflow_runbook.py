from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_live_cockpit_absorbs_research_runbook_operator_steps() -> None:
    runbook = _runbook(endpoint_overrides={"web": "https://search.example.dev/query"})

    result = LiveCockpitRuntime().build(research_workflow_runbook=runbook)

    assert result.decision == "report"
    assert result.research_workflow_runbook is not None
    assert result.research_workflow_runbook_decision == "runbook_ready"
    assert result.research_workflow_runbook_step_count == 1
    assert result.research_workflow_runbook_blocked_reason_count == 0
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-runbook --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_research_runbook_is_blocked() -> None:
    runbook = _blocked_runbook()

    result = LiveCockpitRuntime().build(research_workflow_runbook=runbook)

    assert result.decision == "blocked"
    assert "research-workflow-runbook:live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_research_runbook() -> None:
    runbook = _runbook(endpoint_overrides={"web": "https://search.example.dev/query"})
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-runbook-json",
            runbook.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow_runbook=runbook.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_runbook_decision"] == "runbook_ready"
    assert payload["research_workflow_runbook_step_count"] == 1
    assert payload["network_opened"] is False
    assert library_payload["research_workflow_runbook_step_count"] == 1


def _runbook(*, endpoint_overrides: dict[str, str]):
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave168.objective",
        endpoint_overrides=endpoint_overrides,
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave168",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    review = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave168",
    )
    return LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave168",
    )


def _blocked_runbook():
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave168.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave168"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave168/blocked",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    review = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave168/blocked",
    )
    return LiveResearchWorkflowRunbookRuntime().build(
        review=review,
        runbook_ref="runbook://wave168/blocked",
    )
