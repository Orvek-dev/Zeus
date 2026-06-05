from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusRuntime,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorResult,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
)


def register_wave179_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-execution-status")
    def live_research_workflow_execution_status(
        loopback_executor_json: Optional[str] = typer.Option(None, "--loopback-executor-json"),
        external_execution_json: Optional[str] = typer.Option(None, "--external-execution-json"),
        status_ref: str = typer.Option(..., "--status-ref"),
        evidence_ref: str = typer.Option(..., "--evidence-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            loopback_executor = (
                None
                if loopback_executor_json is None
                else LiveResearchWorkflowLoopbackExecutorResult.model_validate_json(
                    loopback_executor_json
                )
            )
            external_execution = (
                None
                if external_execution_json is None
                else LiveResearchWorkflowExternalExecutionResult.model_validate_json(
                    external_execution_json
                )
            )
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_execution_status"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowExecutionStatusRuntime().build(
            loopback_executor=loopback_executor,
            external_execution=external_execution,
            status_ref=status_ref,
            evidence_ref=evidence_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
