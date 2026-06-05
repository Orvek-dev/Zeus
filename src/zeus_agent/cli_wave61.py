from __future__ import annotations

import json

import typer
from pydantic import ValidationError

from zeus_agent.live_execute_runtime import LiveExecutePlanRequest, LiveExecutePlanRuntime


def register_wave61_commands(app: typer.Typer) -> None:
    @app.command("live-execute-plan")
    def live_execute_plan(
        request_json: str = typer.Option(..., "--request-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            request = LiveExecutePlanRequest.model_validate_json(request_json)
        except (ValidationError, TypeError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execute_plan",
                    "error": str(exc),
                    "execution_allowed": False,
                    "live_production_claimed": False,
                    "network_opened": False,
                    "handler_executed": False,
                },
                as_json=as_json,
            )
            raise typer.Exit(code=1)
        result = LiveExecutePlanRuntime().plan(request)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
