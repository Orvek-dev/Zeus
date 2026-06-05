from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_live_cockpit_absorbs_research_workflow_without_opening_network() -> None:
    workflow = _workflow()

    result = LiveCockpitRuntime().build(research_workflow=workflow)

    assert result.decision == "report"
    assert result.research_workflow is not None
    assert result.research_workflow_decision == "workflow_planned"
    assert result.research_workflow_ready_source_count == 2
    assert result.research_workflow_endpoint_required_count == 1
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_research_workflow_is_blocked() -> None:
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave161.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave161"},
    )

    result = LiveCockpitRuntime().build(research_workflow=workflow)

    assert result.decision == "blocked"
    assert "research-workflow:live_research_workflow_endpoint_contains_secret" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_research_workflow() -> None:
    workflow = _workflow()
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-json",
            workflow.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow=workflow.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_decision"] == "workflow_planned"
    assert payload["research_workflow_ready_source_count"] == 2
    assert payload["network_opened"] is False
    assert library_payload["research_workflow_endpoint_required_count"] == 1


def _workflow():
    return LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave161.objective",
        endpoint_overrides={"web": "https://search.example.dev/query"},
    )
