from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.platform_cockpit_runtime import PlatformCockpitRuntime


def register_wave54_commands(app: typer.Typer) -> None:
    @app.command("platform")
    def platform(
        surface_id: Optional[str] = typer.Option(None, "--surface"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = PlatformCockpitRuntime().build(surface_id=surface_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
