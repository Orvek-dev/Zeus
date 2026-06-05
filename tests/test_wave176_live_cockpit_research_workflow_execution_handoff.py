from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationRuntime,
)
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffRuntime,
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


def test_live_cockpit_absorbs_research_workflow_execution_handoff_ready() -> None:
    handoff = _ready_handoff()

    result = LiveCockpitRuntime().build(research_workflow_execution_handoff=handoff)

    assert result.decision == "report"
    assert result.research_workflow_execution_handoff is not None
    assert result.research_workflow_execution_handoff_decision == "handoff_ready"
    assert result.research_workflow_execution_handoff_ready is True
    assert result.research_workflow_execution_handoff_execution_allowed is True
    assert result.research_workflow_execution_handoff_live_transport_enabled is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-execution-handoff --json" in result.recommended_next_commands


def test_live_cockpit_blocks_when_research_workflow_execution_handoff_is_blocked() -> None:
    handoff = _blocked_handoff()

    result = LiveCockpitRuntime().build(research_workflow_execution_handoff=handoff)

    assert result.decision == "blocked"
    assert "research-workflow-execution-handoff:research_workflow_handoff_preflight_not_ready" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.no_secret_echo is True


def test_cli_and_python_library_live_cockpit_research_workflow_execution_handoff() -> None:
    handoff = _ready_handoff()
    completed = CliRunner().invoke(
        app,
        [
            "live",
            "--research-workflow-execution-handoff-json",
            handoff.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_status(research_workflow_execution_handoff=handoff.to_payload())

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["research_workflow_execution_handoff_decision"] == "handoff_ready"
    assert payload["research_workflow_execution_handoff_execution_allowed"] is True
    assert payload["research_workflow_execution_handoff_live_transport_enabled"] is False
    assert payload["network_opened"] is False
    assert library_payload["research_workflow_execution_handoff_ready"] is True


def _ready_handoff():
    return _handoff(_ready_runbook(), suffix="ready")


def _blocked_handoff():
    return _handoff(_operator_action_runbook(), suffix="blocked")


def _handoff(runbook, suffix: str):
    preflight_plan = LiveResearchWorkflowPreflightPlanRuntime().build(
        runbook=runbook,
        preflight_ref="research-preflight://wave176/{0}".format(suffix),
    )
    authorization = LiveResearchWorkflowAuthorizationRuntime().authorize(
        preflight_plan=preflight_plan,
        authorization_ref="research-authorization://wave176/{0}".format(suffix),
        operator_approval_ref="operator-approval://wave176/{0}".format(suffix),
        evidence_ref="evidence://wave176/{0}".format(suffix),
    )
    executor_release = LiveResearchWorkflowExecutorReleaseRuntime().release(
        authorization=authorization,
        release_ref="research-release://wave176/{0}".format(suffix),
        idempotency_key="wave176-{0}".format(suffix),
    )
    return LiveResearchWorkflowExecutionHandoffRuntime().build(
        preflight_plan=preflight_plan,
        authorization=authorization,
        executor_release=executor_release,
        handoff_ref="research-execution-handoff://wave176/{0}".format(suffix),
    )
