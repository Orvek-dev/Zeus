from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
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


def test_live_cockpit_absorbs_research_workflow_executor_release_ready() -> None:
    release = _ready_release()

    result = LiveCockpitRuntime().build(research_workflow_executor_release=release)

    assert result.decision == "report"
    assert result.research_workflow_executor_release is not None
    assert result.research_workflow_executor_release_decision == "release_ready"
    assert result.research_workflow_executor_release_ready is True
    assert result.research_workflow_executor_release_granted is True
    assert result.research_workflow_executor_release_execution_allowed is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-executor-release --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_research_workflow_executor_release_is_blocked() -> None:
    release = _blocked_release()

    result = LiveCockpitRuntime().build(research_workflow_executor_release=release)

    assert result.decision == "blocked"
    assert "research-workflow-executor-release:research_workflow_authorization_not_ready" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_research_workflow_executor_release() -> None:
    release = _ready_release()
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-executor-release-json",
            release.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow_executor_release=release.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_executor_release_decision"] == "release_ready"
    assert payload["research_workflow_executor_release_ready"] is True
    assert payload["research_workflow_executor_release_execution_allowed"] is True
    assert payload["network_opened"] is False
    assert library_payload["research_workflow_executor_release_granted"] is True


def _ready_release():
    return LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=_authorization(_ready_runbook(), "ready"),
        release_ref="research-release://wave174/ready",
        idempotency_key="wave174-ready",
    )


def _blocked_release():
    return LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=_authorization(_operator_action_runbook(), "blocked"),
        release_ref="research-release://wave174/blocked",
        idempotency_key="wave174-blocked",
    )


def _authorization(runbook, suffix: str):
    plan = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref=f"research-preflight://wave174/{suffix}",
    )
    return LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref=f"research-authorization://wave174/{suffix}",
        operator_approval_ref=f"operator-approval://wave174/{suffix}",
        evidence_ref=f"evidence://wave174/{suffix}",
    )
