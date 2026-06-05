from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult


def register_wave90_commands(app: typer.Typer) -> None:
    @app.command("live-secret-material-check")
    def live_secret_material_check(
        transport_lease_json: str = typer.Option(..., "--transport-lease-json"),
        secret_ref: str = typer.Option(..., "--secret-ref"),
        allow_material_access: bool = typer.Option(False, "--allow-material-access"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            transport_lease = LiveTransportLeaseResult.model_validate_json(transport_lease_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_secret_material_check",
                    "error": str(exc),
                    "credential_material_accessed": False,
                    "raw_secret_returned": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveSecretMaterialRuntime().check(
            transport_lease=transport_lease,
            secret_ref=secret_ref,
            allow_material_access=allow_material_access,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
