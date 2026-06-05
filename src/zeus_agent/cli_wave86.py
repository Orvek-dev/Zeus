from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_provider_execution_runtime import LiveProviderExecutionRuntime


def register_wave86_commands(app: typer.Typer) -> None:
    @app.command("live-provider-generate")
    def live_provider_generate(
        readiness_json: str = typer.Option(..., "--readiness-json"),
        provider_kind: str = typer.Option("fake", "--provider-kind"),
        message: str = typer.Option(..., "--message"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            readiness = LiveExecutionReadinessResult.model_validate_json(readiness_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execution_readiness",
                    "errors": json.loads(exc.json()),
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProviderExecutionRuntime().generate(
            readiness=readiness,
            provider_kind=provider_kind,
            message=message,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
