from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.real_provider_runtime import build_real_provider_contract


def register_wave310_commands(app: typer.Typer) -> None:
    @app.command("provider-runtime")
    def provider_runtime(
        scenario: str = typer.Option("status", "--scenario"),
        endpoint: str = typer.Option("https://api.openai.local/v1/chat/completions", "--endpoint"),
        allowed_host: str = typer.Option("api.openai.local", "--allowed-host"),
        secret_ref: str = typer.Option("env://ZEUS_V110_PROVIDER_KEY", "--secret-ref"),
        model_id: str = typer.Option("gpt-v110-provider", "--model-id"),
        message: str = typer.Option("summarize Zeus real provider runtime", "--message"),
        budget_limit: int = typer.Option(8, "--budget-limit"),
        budget_requested: int = typer.Option(2, "--budget-requested"),
        timeout_ms: int = typer.Option(1500, "--timeout-ms"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_real_provider_contract(
            scenario=scenario,
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            model_id=model_id,
            message=message,
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
