from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_mcp_execution_runtime import LiveMcpExecutionRuntime


def register_wave87_commands(app: typer.Typer) -> None:
    @app.command("live-mcp-invoke")
    def live_mcp_invoke(
        readiness_json: str = typer.Option(..., "--readiness-json"),
        tool_name: str = typer.Option(..., "--tool-name"),
        arguments_json: str = typer.Option("{}", "--arguments-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            readiness = LiveExecutionReadinessResult.model_validate_json(readiness_json)
            arguments = json.loads(arguments_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_mcp_invocation",
                    "error": str(exc),
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        if not isinstance(arguments, dict):
            arguments = {}
        result = LiveMcpExecutionRuntime().invoke(
            readiness=readiness,
            tool_name=tool_name,
            arguments=arguments,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
