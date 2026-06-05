from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_workflow_authorization_runtime import LiveResearchWorkflowAuthorizationResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffRuntime,
)
from zeus_agent.live_research_workflow_executor_release_runtime import (
    LiveResearchWorkflowExecutorReleaseResult,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanResult


def register_wave175_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-execution-handoff")
    def live_research_workflow_execution_handoff(
        preflight_plan_json: str = typer.Option(..., "--preflight-plan-json"),
        authorization_json: str = typer.Option(..., "--authorization-json"),
        executor_release_json: str = typer.Option(..., "--executor-release-json"),
        handoff_ref: str = typer.Option(..., "--handoff-ref"),
        operator_note: Optional[str] = typer.Option(None, "--operator-note"),
        production_release_requested: bool = typer.Option(False, "--production-release-requested"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            preflight_plan = LiveResearchWorkflowPreflightPlanResult.model_validate_json(
                preflight_plan_json
            )
            authorization = LiveResearchWorkflowAuthorizationResult.model_validate_json(authorization_json)
            executor_release = LiveResearchWorkflowExecutorReleaseResult.model_validate_json(
                executor_release_json
            )
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "handoff_ref": handoff_ref,
                    "blocked_reasons": ["malformed_live_research_workflow_execution_handoff"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowExecutionHandoffRuntime().build(
            preflight_plan=preflight_plan,
            authorization=authorization,
            executor_release=executor_release,
            handoff_ref=handoff_ref,
            operator_note=operator_note,
            production_release_requested=production_release_requested,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
