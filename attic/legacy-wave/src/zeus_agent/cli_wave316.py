from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.real_product_platform_runtime import build_real_product_platform_contract


def register_wave316_commands(app: typer.Typer) -> None:
    @app.command("product-platform-runtime")
    def product_platform_runtime(
        scenario: str = typer.Option("status", "--scenario"),
        home: Optional[Path] = typer.Option(None, "--home"),
        operator_note: Optional[str] = typer.Option(None, "--operator-note"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_real_product_platform_contract(
            scenario=scenario,
            home=home,
            operator_note=operator_note,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
