from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.provider_owned_client_live_runtime import build_provider_owned_client_live_contract


def register_wave307_commands(app: typer.Typer) -> None:
    @app.command("provider-owned-client-live")
    def provider_owned_client_live(
        scenario: str = typer.Option("status", "--scenario"),
        endpoint: str = typer.Option("https://api.openai.local/v1/chat/completions", "--endpoint"),
        allowed_host: str = typer.Option("api.openai.local", "--allowed-host"),
        secret_ref: str = typer.Option("env://ZEUS_RC8_PROVIDER_KEY", "--secret-ref"),
        model_id: str = typer.Option("gpt-rc8-owned-client", "--model-id"),
        message: str = typer.Option("summarize provider owned client live checkpoint", "--message"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_provider_owned_client_live_contract(
            scenario=scenario,
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            model_id=model_id,
            message=message,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
