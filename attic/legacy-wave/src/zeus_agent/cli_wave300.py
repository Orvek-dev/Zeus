from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.production_foundation_runtime import build_production_foundation_contract


def register_wave300_commands(app: typer.Typer) -> None:
    @app.command("production-foundation")
    def production_foundation(
        home: Optional[Path] = typer.Option(None, "--home"),
        include_credentials: bool = typer.Option(False, "--include-credentials"),
        operator_note: Optional[str] = typer.Option(None, "--operator-note"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_production_foundation_contract(
            home=home or default_zeus_home(),
            include_credentials=include_credentials,
            operator_note=operator_note,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
