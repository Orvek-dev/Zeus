from __future__ import annotations

import json

import typer

from zeus_agent.eval.wave5 import run_wave5_eval
from zeus_agent.wave5_scenarios import (
    wave5_connector_payload,
    wave5_provider_payload,
)


def register_wave5_commands(app: typer.Typer) -> None:
    @app.command("wave5-providers")
    def wave5_providers(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave5_provider_payload(), as_json=as_json)

    @app.command("wave5-connectors")
    def wave5_connectors(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave5_connector_payload(), as_json=as_json)

    @app.command("wave5-eval")
    def wave5_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave5_eval(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
