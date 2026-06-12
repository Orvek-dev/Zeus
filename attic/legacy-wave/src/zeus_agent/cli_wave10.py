from __future__ import annotations

import json
from typing import Union

import typer

from zeus_agent.eval.wave10 import Wave10EvalPayload, run_wave10_eval
from zeus_agent.wave10_provider_scenarios import (
    Wave10Payload,
    wave10_provider_blocks_payload,
    wave10_provider_happy_payload,
)


def register_wave10_commands(app: typer.Typer) -> None:
    @app.command("wave10-provider")
    def wave10_provider(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave10_provider_happy_payload(), as_json=as_json)

    @app.command("wave10-blocks")
    def wave10_blocks(
        secret_like: str = typer.Option(
            "sk-wave10-secret",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave10_provider_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave10-eval")
    def wave10_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave10_eval(), as_json=as_json)


def _print_payload(
    payload: Union[Wave10Payload, Wave10EvalPayload],
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
