from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorRuntime,
)


def register_wave177_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-loopback-executor")
    def live_research_workflow_loopback_executor(
        handoff_json: str = typer.Option(..., "--handoff-json"),
        plan_json: str = typer.Option(..., "--plan-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            handoff = LiveResearchWorkflowExecutionHandoffResult.model_validate_json(handoff_json)
            plan = LiveResearchExecutionPlanResult.model_validate_json(plan_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_loopback_executor"],
                    "error": str(exc),
                    "live_transport_enabled": False,
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowLoopbackExecutorRuntime().execute(handoff=handoff, plan=plan)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
