from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.real_self_evolution_runtime import build_real_self_evolution_contract


def register_wave315_commands(app: typer.Typer) -> None:
    @app.command("self-evolution-runtime")
    def self_evolution_runtime(
        scenario: str = typer.Option("status", "--scenario"),
        home: Optional[Path] = typer.Option(None, "--home"),
        objective: str = typer.Option(
            "Improve Zeus governed workflow efficiency from verified eval evidence.",
            "--objective",
        ),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_real_self_evolution_contract(
            scenario=scenario,
            home=home,
            objective=objective,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
