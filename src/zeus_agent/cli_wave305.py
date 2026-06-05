from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.memory_privacy_live_runtime import build_memory_privacy_live_contract


def register_wave305_commands(app: typer.Typer) -> None:
    @app.command("memory-privacy-live")
    def memory_privacy_live(
        scenario: str = typer.Option("status", "--scenario"),
        home: Path = typer.Option(default_zeus_home(), "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_memory_privacy_live_contract(
            scenario=scenario,
            home=home,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
