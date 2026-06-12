from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_provider_request_body_runtime import LiveProviderRequestBodyRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult


def register_wave128_commands(app: typer.Typer) -> None:
    @app.command("live-provider-request-body")
    def live_provider_request_body(
        provider_envelope_json: str = typer.Option(..., "--provider-envelope-json"),
        message: str = typer.Option(..., "--message"),
        body_ref: str = typer.Option(..., "--body-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            provider_envelope = LiveProviderRequestResult.model_validate_json(provider_envelope_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_provider_request_body",
                    "error": str(exc),
                    "network_opened": False,
                    "raw_secret_returned": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProviderRequestBodyRuntime().materialize(
            provider_envelope=provider_envelope,
            message=message,
            body_ref=body_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
