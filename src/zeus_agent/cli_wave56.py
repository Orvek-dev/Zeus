from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.persona_cockpit_runtime import PersonaCockpitRuntime


def register_wave56_commands(app: typer.Typer) -> None:
    @app.command("persona")
    def persona(
        home: Optional[Path] = typer.Option(None, "--home"),
        profile: Optional[str] = typer.Option(None, "--profile"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = PersonaCockpitRuntime(home or default_zeus_home()).build(profile=profile)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
