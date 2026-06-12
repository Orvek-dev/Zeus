from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.sandbox_terminal_live_runtime import build_sandbox_terminal_live_contract


def register_wave304_commands(app: typer.Typer) -> None:
    @app.command("sandbox-terminal-live")
    def sandbox_terminal_live(
        scenario: str = typer.Option("status", "--scenario"),
        command: str = typer.Option("pwd", "--command"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_sandbox_terminal_live_contract(
            scenario=scenario,
            command=command,
            home=home,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
