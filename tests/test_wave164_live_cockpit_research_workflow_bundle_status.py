from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_live_cockpit_absorbs_workflow_bundle_status_endpoint_gaps() -> None:
    status = _bundle_status(endpoint_overrides={"web": "https://search.example.dev/query"})

    result = LiveCockpitRuntime().build(research_workflow_bundle_status=status)

    assert result.decision == "report"
    assert result.research_workflow_bundle_status is not None
    assert result.research_workflow_bundle_decision == "endpoint_gaps"
    assert result.research_workflow_bundle_planned_source_count == 2
    assert result.research_workflow_bundle_endpoint_required_count == 1
    assert result.research_workflow_bundle_blocked_source_count == 0
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-bundle-status --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_workflow_bundle_status_is_blocked() -> None:
    status = _blocked_bundle_status()

    result = LiveCockpitRuntime().build(research_workflow_bundle_status=status)

    assert result.decision == "blocked"
    assert "research-workflow-bundle:live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_workflow_bundle_status() -> None:
    status = _bundle_status(endpoint_overrides={"web": "https://search.example.dev/query"})
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-bundle-status-json",
            status.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow_bundle_status=status.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_bundle_decision"] == "endpoint_gaps"
    assert payload["research_workflow_bundle_endpoint_required_count"] == 1
    assert payload["network_opened"] is False
    assert library_payload["research_workflow_bundle_decision"] == "endpoint_gaps"


def _bundle_status(*, endpoint_overrides: dict[str, str]):
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave164.objective",
        endpoint_overrides=endpoint_overrides,
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave164",
    )
    return LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)


def _blocked_bundle_status():
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave164.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave164"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave164/blocked",
    )
    return LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
