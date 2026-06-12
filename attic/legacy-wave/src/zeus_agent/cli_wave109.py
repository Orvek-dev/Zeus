from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_mcp_http_transport_runtime import LiveMcpHttpTransportRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult


def register_wave109_commands(app: typer.Typer) -> None:
    @app.command("live-mcp-http-transport")
    def live_mcp_http_transport(
        activation_json: str = typer.Option(..., "--activation-json"),
        adapter_plan_json: str = typer.Option(..., "--adapter-plan-json"),
        mcp_envelope_json: str = typer.Option(..., "--mcp-envelope-json"),
        transport_kind: str = typer.Option("local_http", "--transport-kind"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            activation = LiveTransportActivationResult.model_validate_json(activation_json)
            adapter_plan = LiveMcpAdapterResult.model_validate_json(adapter_plan_json)
            mcp_envelope = LiveMcpRequestResult.model_validate_json(mcp_envelope_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_mcp_http_transport",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveMcpHttpTransportRuntime().execute(
            activation=activation,
            adapter_plan=adapter_plan,
            mcp_envelope=mcp_envelope,
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
