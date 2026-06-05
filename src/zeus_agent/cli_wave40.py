from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.live_smoke_runtime import run_live_optin_smoke


def register_wave40_commands(app: typer.Typer) -> None:
    @app.command("live-optin-smoke")
    def live_optin_smoke(
        scenario: str = typer.Option("happy", "--scenario"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        if scenario not in {"happy", "blocked"}:
            raise typer.BadParameter("scenario must be one of: happy, blocked")
        result = run_live_optin_smoke(scenario=scenario)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
