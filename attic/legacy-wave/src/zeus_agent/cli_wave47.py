from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.runtime_cockpit import RuntimeCockpitRuntime


def register_wave47_commands(app: typer.Typer) -> None:
    @app.command("runtime")
    def runtime(
        backend_id: Optional[str] = typer.Option(None, "--backend"),
        root: Optional[Path] = typer.Option(None, "--root"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = RuntimeCockpitRuntime().build(backend_id=backend_id, root=root)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
