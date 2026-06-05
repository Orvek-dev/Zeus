from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.live_research_adapter_catalog_runtime import live_research_adapter_catalog_payload


def register_wave154_commands(app: typer.Typer) -> None:
    @app.command("live-research-adapters")
    def live_research_adapters(
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        _print_payload(live_research_adapter_catalog_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
