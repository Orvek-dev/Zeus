from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_gateway_loopback_transport_runtime import LiveGatewayLoopbackTransportRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult


def register_wave103_commands(app: typer.Typer) -> None:
    @app.command("live-gateway-loopback-transport")
    def live_gateway_loopback_transport(
        activation_json: str = typer.Option(..., "--activation-json"),
        adapter_plan_json: str = typer.Option(..., "--adapter-plan-json"),
        gateway_envelope_json: str = typer.Option(..., "--gateway-envelope-json"),
        transport_kind: str = typer.Option("loopback_delivery", "--transport-kind"),
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
                    "reason": "malformed_live_gateway_loopback_transport",
                    "error": str(exc),
                    "delivery_attempted": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveGatewayLoopbackTransportRuntime().execute(
            activation=activation,
            adapter_plan=adapter_plan,
            gateway_envelope=gateway_envelope,
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
