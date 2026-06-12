from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationRuntime,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import (
    LiveResearchWorkflowPreflightPlanRuntime,
)
from tests.test_wave169_live_research_workflow_preflight_plan import (
    _blocked_runbook,
    _ready_runbook,
)


def test_live_cockpit_absorbs_research_workflow_authorization_ready() -> None:
    authorization = _ready_authorization()

    result = LiveCockpitRuntime().build(research_workflow_authorization=authorization)

    assert result.decision == "report"
    assert result.research_workflow_authorization is not None
    assert result.research_workflow_authorization_decision == "authorization_ready"
    assert result.research_workflow_authorization_ready is True
    assert result.research_workflow_authorized_candidate_count == 1
    assert result.research_workflow_authorization_executor_release_granted is False
    assert result.research_workflow_authorization_execution_allowed is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-authorization --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_research_workflow_authorization_is_blocked() -> None:
    authorization = _blocked_authorization()

    result = LiveCockpitRuntime().build(research_workflow_authorization=authorization)

    assert result.decision == "blocked"
    assert "research-workflow-authorization:live_research_preflight_plan_blocked" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_research_workflow_authorization() -> None:
    authorization = _ready_authorization()
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-authorization-json",
            authorization.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow_authorization=authorization.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_authorization_decision"] == "authorization_ready"
    assert payload["research_workflow_authorization_ready"] is True
    assert payload["research_workflow_authorized_candidate_count"] == 1
    assert payload["research_workflow_authorization_execution_allowed"] is False
    assert library_payload["research_workflow_authorization_ready"] is True


def _ready_authorization():
    plan = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=_ready_runbook(),
        preflight_ref="research-preflight://wave172/ready",
    )
    return LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave172/ready",
        operator_approval_ref="operator-approval://wave172/ready",
        evidence_ref="evidence://wave172/ready",
    )


def _blocked_authorization():
    plan = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=_blocked_runbook(),
        preflight_ref="research-preflight://wave172/blocked",
    )
    return LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=plan,
        authorization_ref="research-authorization://wave172/blocked",
        operator_approval_ref="operator-approval://wave172/blocked",
        evidence_ref="evidence://wave172/blocked",
    )
