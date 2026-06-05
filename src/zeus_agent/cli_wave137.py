from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_registry_runtime import LiveExecutionRegistryRuntime
from zeus_agent.live_execution_status_runtime import LiveExecutionStatusResult


def register_wave137_commands(app: typer.Typer) -> None:
    @app.command("live-execution-record")
    def live_execution_record(
        status_json: str = typer.Option(..., "--status-json"),
        record_ref: str = typer.Option(..., "--record-ref"),
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            status = LiveExecutionStatusResult.model_validate_json(status_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execution_record",
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveExecutionRegistryRuntime(home).record(status=status, record_ref=record_ref)
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-execution-records")
    def live_execution_records(
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveExecutionRegistryRuntime(home).list()
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
