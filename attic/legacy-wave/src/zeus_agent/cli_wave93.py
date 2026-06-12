from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult


def register_wave93_commands(app: typer.Typer) -> None:
    @app.command("live-mcp-request-envelope")
    def live_mcp_request_envelope(
        transport_lease_json: str = typer.Option(..., "--transport-lease-json"),
        secret_material_json: str = typer.Option(..., "--secret-material-json"),
        server_id: str = typer.Option(..., "--server-id"),
        tool_name: str = typer.Option(..., "--tool-name"),
        endpoint: str = typer.Option(..., "--endpoint"),
        arguments_json: str = typer.Option("{}", "--arguments-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            transport_lease = LiveTransportLeaseResult.model_validate_json(transport_lease_json)
            secret_material = LiveSecretMaterialResult.model_validate_json(secret_material_json)
            arguments = json.loads(arguments_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_mcp_request_envelope",
                    "error": str(exc),
                    "server_started": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        if not isinstance(arguments, dict):
            arguments = {}
        result = LiveMcpRequestRuntime().prepare(
            transport_lease=transport_lease,
            secret_material=secret_material,
            server_id=server_id,
            tool_name=tool_name,
            endpoint=endpoint,
            arguments=arguments,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
