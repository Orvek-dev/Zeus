from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessRuntime
from zeus_agent.live_execute_runtime import LiveExecutePlanResult


def register_wave85_commands(app: typer.Typer) -> None:
    @app.command("live-execution-readiness")
    def live_execution_readiness(
        execute_plan_json: str = typer.Option(..., "--execute-plan-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            execute_plan = LiveExecutePlanResult.model_validate_json(execute_plan_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execute_plan",
                    "errors": json.loads(exc.json()),
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveExecutionReadinessRuntime().evaluate(execute_plan)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
