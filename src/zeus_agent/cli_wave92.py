from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult


def register_wave92_commands(app: typer.Typer) -> None:
    @app.command("live-gateway-delivery-envelope")
    def live_gateway_delivery_envelope(
        transport_lease_json: str = typer.Option(..., "--transport-lease-json"),
        secret_material_json: str = typer.Option(..., "--secret-material-json"),
        adapter_id: str = typer.Option(..., "--adapter-id"),
        target: str = typer.Option(..., "--target"),
        message: str = typer.Option(..., "--message"),
        idempotency_key: str = typer.Option(..., "--idempotency-key"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            transport_lease = LiveTransportLeaseResult.model_validate_json(transport_lease_json)
            secret_material = LiveSecretMaterialResult.model_validate_json(secret_material_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_gateway_delivery_envelope",
                    "error": str(exc),
                    "external_delivery_opened": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveGatewayDeliveryRuntime().prepare(
            transport_lease=transport_lease,
            secret_material=secret_material,
            adapter_id=adapter_id,
            target=target,
            message=message,
            idempotency_key=idempotency_key,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
