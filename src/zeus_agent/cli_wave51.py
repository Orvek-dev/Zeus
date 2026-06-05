from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.plugin_cockpit_runtime import PluginCockpitRuntime


def register_wave51_commands(app: typer.Typer) -> None:
    @app.command("plugins")
    def plugins(
        plugin_id: Optional[str] = typer.Option(None, "--plugin-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = PluginCockpitRuntime().build(plugin_id=plugin_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
