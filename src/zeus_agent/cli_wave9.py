from __future__ import annotations

import json

import typer

from zeus_agent.eval.wave9 import run_wave9_eval
from zeus_agent.wave9_scenarios import (
    wave9_runtime_blocks_payload,
    wave9_runtime_lease_payload,
)


def register_wave9_commands(app: typer.Typer) -> None:
    @app.command("wave9-lease")
    def wave9_lease(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave9_runtime_lease_payload(), as_json=as_json)

    @app.command("wave9-blocks")
    def wave9_blocks(
        secret_like: str = typer.Option(
            "sk-wave9-secret",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave9_runtime_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave9-eval")
    def wave9_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave9_eval(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
