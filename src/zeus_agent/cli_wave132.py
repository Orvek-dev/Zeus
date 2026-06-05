from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_mcp_request_body_runtime import LiveMcpRequestBodyRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult


def register_wave132_commands(app: typer.Typer) -> None:
    @app.command("live-mcp-request-body")
    def live_mcp_request_body(
        mcp_envelope_json: str = typer.Option(..., "--mcp-envelope-json"),
        arguments_json: str = typer.Option(..., "--arguments-json"),
        body_ref: str = typer.Option(..., "--body-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            mcp_envelope = LiveMcpRequestResult.model_validate_json(mcp_envelope_json)
            arguments = json.loads(arguments_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_mcp_request_body",
                    "error": str(exc),
                    "network_opened": False,
                    "raw_secret_returned": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveMcpRequestBodyRuntime().materialize(
            mcp_envelope=mcp_envelope,
            arguments=arguments,
            body_ref=body_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
