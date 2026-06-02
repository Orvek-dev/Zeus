from __future__ import annotations

import json
from pathlib import Path

import typer

from zeus_agent.eval.wave13 import Wave13EvalPayload, run_wave13_eval
from zeus_agent.wave13_production_scenarios import (
    Wave13Payload,
    wave13_blocks_payload,
    wave13_production_payload,
)


def register_wave13_commands(app: typer.Typer) -> None:
    @app.command("wave13-production")
    def wave13_production(
        home: Path = typer.Option(
            Path(".wave13-state"),
            "--home",
            help="Local state home used for Wave13 draft records.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave13_production_payload(home=home), as_json=as_json)

    @app.command("wave13-blocks")
    def wave13_blocks(
        secret_like: str = typer.Option(
            "redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        home: Path = typer.Option(
            Path(".wave13-state"),
            "--home",
            help="Local state home used for Wave13 block records.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave13_blocks_payload(home=home, raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave13-eval")
    def wave13_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave13_eval(), as_json=as_json)


def _print_payload(
    payload: Wave13Payload | Wave13EvalPayload,
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
