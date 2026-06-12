from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_gateway_http_transport_runtime import LiveGatewayHttpTransportRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult


def register_wave108_commands(app: typer.Typer) -> None:
    @app.command("live-gateway-http-transport")
    def live_gateway_http_transport(
        activation_json: str = typer.Option(..., "--activation-json"),
        adapter_plan_json: str = typer.Option(..., "--adapter-plan-json"),
        gateway_envelope_json: str = typer.Option(..., "--gateway-envelope-json"),
        delivery_endpoint: str = typer.Option(..., "--delivery-endpoint"),
        transport_kind: str = typer.Option("local_http", "--transport-kind"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            activation = LiveTransportActivationResult.model_validate_json(activation_json)
            adapter_plan = LiveGatewayAdapterResult.model_validate_json(adapter_plan_json)
            gateway_envelope = LiveGatewayDeliveryResult.model_validate_json(gateway_envelope_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_gateway_http_transport",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveGatewayHttpTransportRuntime().execute(
            activation=activation,
            adapter_plan=adapter_plan,
            gateway_envelope=gateway_envelope,
            delivery_endpoint=delivery_endpoint,
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
