from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_sealed_credential_runtime import (
    LiveSealedCredentialRuntime,
    StaticSealedCredentialConsumer,
)
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult


def register_wave127_commands(app: typer.Typer) -> None:
    @app.command("live-sealed-credential-release")
    def live_sealed_credential_release(
        injection_json: str = typer.Option(..., "--injection-json"),
        secret_material_json: str = typer.Option(..., "--secret-material-json"),
        consumer_ref: str = typer.Option(..., "--consumer-ref"),
        release_ref: str = typer.Option(..., "--release-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            injection = LiveCredentialInjectionResult.model_validate_json(injection_json)
            secret_material = LiveSecretMaterialResult.model_validate_json(secret_material_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_sealed_credential_release",
                    "error": str(exc),
                    "credential_material_accessed": False,
                    "raw_secret_returned": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveSealedCredentialRuntime().release(
            injection=injection,
            secret_material=secret_material,
            consumer=StaticSealedCredentialConsumer(consumer_ref),
            release_ref=release_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
