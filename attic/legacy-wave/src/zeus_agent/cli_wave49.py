from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.security_cockpit_runtime import SecurityCockpitRuntime


def register_wave49_commands(app: typer.Typer) -> None:
    @app.command("security")
    def security(
        control_id: Optional[str] = typer.Option(None, "--control-id"),
        include_credentials: bool = typer.Option(False, "--include-credentials"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = SecurityCockpitRuntime(home=home or default_zeus_home()).build(
            control_id=control_id,
            include_credentials=include_credentials,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
