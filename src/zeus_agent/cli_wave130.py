from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_delivery_body_runtime import LiveGatewayDeliveryBodyRuntime
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult


def register_wave130_commands(app: typer.Typer) -> None:
    @app.command("live-gateway-delivery-body")
    def live_gateway_delivery_body(
        gateway_envelope_json: str = typer.Option(..., "--gateway-envelope-json"),
        message: str = typer.Option(..., "--message"),
        body_ref: str = typer.Option(..., "--body-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            gateway_envelope = LiveGatewayDeliveryResult.model_validate_json(gateway_envelope_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_gateway_delivery_body",
                    "error": str(exc),
                    "network_opened": False,
                    "raw_secret_returned": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveGatewayDeliveryBodyRuntime().materialize(
            gateway_envelope=gateway_envelope,
            message=message,
            body_ref=body_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
