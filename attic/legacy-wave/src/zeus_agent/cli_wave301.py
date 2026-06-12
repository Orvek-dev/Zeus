from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.provider_live_api_runtime import build_provider_live_api_contract


def register_wave301_commands(app: typer.Typer) -> None:
    @app.command("provider-live-api")
    def provider_live_api(
        scenario: str = typer.Option("status", "--scenario"),
        secret_ref: str = typer.Option("env://ZEUS_RC2_PROVIDER_KEY", "--secret-ref"),
        message: str = typer.Option("summarize provider live api checkpoint", "--message"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_provider_live_api_contract(
            scenario=scenario,
            secret_ref=secret_ref,
            message=message,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
