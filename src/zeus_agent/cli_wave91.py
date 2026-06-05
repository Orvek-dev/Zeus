from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult


def register_wave91_commands(app: typer.Typer) -> None:
    @app.command("live-provider-request-envelope")
    def live_provider_request_envelope(
        transport_lease_json: str = typer.Option(..., "--transport-lease-json"),
        secret_material_json: str = typer.Option(..., "--secret-material-json"),
        provider_kind: str = typer.Option(..., "--provider-kind"),
        model_id: str = typer.Option(..., "--model-id"),
        endpoint: str = typer.Option(..., "--endpoint"),
        message: str = typer.Option(..., "--message"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            transport_lease = LiveTransportLeaseResult.model_validate_json(transport_lease_json)
            secret_material = LiveSecretMaterialResult.model_validate_json(secret_material_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_provider_request_envelope",
                    "error": str(exc),
                    "provider_invoked": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProviderRequestRuntime().prepare(
            transport_lease=transport_lease,
            secret_material=secret_material,
            provider_kind=provider_kind,
            model_id=model_id,
            endpoint=endpoint,
            message=message,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
