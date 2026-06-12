from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_gateway_execution_runtime import LiveGatewayExecutionRuntime


def register_wave88_commands(app: typer.Typer) -> None:
    @app.command("live-gateway-dispatch")
    def live_gateway_dispatch(
        readiness_json: str = typer.Option(..., "--readiness-json"),
        adapter_id: str = typer.Option(..., "--adapter-id"),
        target: str = typer.Option(..., "--target"),
        message: str = typer.Option(..., "--message"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            readiness = LiveExecutionReadinessResult.model_validate_json(readiness_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_gateway_dispatch",
                    "error": str(exc),
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveGatewayExecutionRuntime().dispatch(
            readiness=readiness,
            adapter_id=adapter_id,
            target=target,
            message=message,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
