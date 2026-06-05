from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_workflow_execution_registry_runtime import (
    LiveResearchWorkflowExecutionRegistryRuntime,
)
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusResult,
)


def register_wave180_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-execution-record")
    def live_research_workflow_execution_record(
        status_json: str = typer.Option(..., "--status-json"),
        record_ref: str = typer.Option(..., "--record-ref"),
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            status = LiveResearchWorkflowExecutionStatusResult.model_validate_json(status_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_execution_record"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowExecutionRegistryRuntime(home).record(
            status=status,
            record_ref=record_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-execution-records")
    def live_research_workflow_execution_records(
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveResearchWorkflowExecutionRegistryRuntime(home).list()
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-execution-record-delete")
    def live_research_workflow_execution_record_delete(
        record_id: str = typer.Option(..., "--record-id"),
        deletion_ref: str = typer.Option(..., "--deletion-ref"),
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveResearchWorkflowExecutionRegistryRuntime(home).delete(
            record_id=record_id,
            deletion_ref=deletion_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
