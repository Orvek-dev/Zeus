from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.real_memory_operation_runtime import build_real_memory_operation_contract


def register_wave314_commands(app: typer.Typer) -> None:
    @app.command("memory-operation")
    def memory_operation(
        scenario: str = typer.Option("status", "--scenario"),
        home: Optional[Path] = typer.Option(None, "--home"),
        subject: str = typer.Option("Zeus", "--subject"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_real_memory_operation_contract(
            scenario=scenario,
            home=home,
            subject=subject,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
