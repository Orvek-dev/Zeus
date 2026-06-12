from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from zeus_agent.production_scale_platform_runtime import build_production_scale_platform_contract


def register_wave321_commands(app: typer.Typer) -> None:
    @app.command("production-scale-platform")
    def production_scale_platform(
        scenario: str = typer.Option("status", "--scenario"),
        home: Optional[Path] = typer.Option(None, "--home"),
        operator_note: Optional[str] = typer.Option(None, "--operator-note"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_production_scale_platform_contract(
            scenario=scenario,
            home=home,
            operator_note=operator_note,
        ).to_payload()
        if as_json:
            typer.echo(json.dumps(payload))
            return
        typer.echo(payload)
