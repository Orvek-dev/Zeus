from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_provider_credentialed_http_runtime import LiveProviderCredentialedHttpRuntime
from zeus_agent.live_provider_request_body_runtime import LiveProviderRequestBodyResult
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult


def register_wave129_commands(app: typer.Typer) -> None:
    @app.command("live-provider-credentialed-http")
    def live_provider_credentialed_http(
        injection_json: str = typer.Option(..., "--injection-json"),
        secret_material_json: str = typer.Option(..., "--secret-material-json"),
        provider_envelope_json: str = typer.Option(..., "--provider-envelope-json"),
        request_body_json: str = typer.Option(..., "--request-body-json"),
        transport_endpoint: str = typer.Option(..., "--transport-endpoint"),
        timeout_ms: int = typer.Option(1500, "--timeout-ms"),
        release_ref: str = typer.Option(..., "--release-ref"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            injection = LiveCredentialInjectionResult.model_validate_json(injection_json)
            secret_material = LiveSecretMaterialResult.model_validate_json(secret_material_json)
            provider_envelope = LiveProviderRequestResult.model_validate_json(provider_envelope_json)
            request_body = LiveProviderRequestBodyResult.model_validate_json(request_body_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_provider_credentialed_http",
                    "error": str(exc),
                    "credential_material_accessed": False,
                    "network_opened": False,
                    "raw_secret_returned": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProviderCredentialedHttpRuntime().execute(
            injection=injection,
            secret_material=secret_material,
            provider_envelope=provider_envelope,
            request_body=request_body,
            transport_endpoint=transport_endpoint,
            timeout_ms=timeout_ms,
            release_ref=release_ref,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
