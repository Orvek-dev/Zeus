from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from zeus_agent.productized_zeus_platform_runtime import build_productized_zeus_platform_contract


def register_wave323_commands(app: typer.Typer) -> None:
    @app.command("productized-platform")
    def productized_platform(
        scenario: str = typer.Option("status", "--scenario"),
        home: Optional[Path] = typer.Option(None, "--home"),
        operator_note: Optional[str] = typer.Option(None, "--operator-note"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_productized_zeus_platform_contract(
            scenario=scenario,
            home=home,
            operator_note=operator_note,
        ).to_payload()
        if as_json:
            typer.echo(json.dumps(payload))
            return
        typer.echo(json.dumps(payload, indent=2))
