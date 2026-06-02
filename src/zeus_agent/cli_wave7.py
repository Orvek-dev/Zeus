from __future__ import annotations

import json

import typer

from zeus_agent.eval.wave7 import run_wave7_eval
from zeus_agent.wave7_scenarios import (
    wave7_policy_blocks_payload,
    wave7_transport_registry_payload,
)


def register_wave7_commands(app: typer.Typer) -> None:
    @app.command("wave7-registry")
    def wave7_registry(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave7_transport_registry_payload(), as_json=as_json)

    @app.command("wave7-policy")
    def wave7_policy(
        secret_like: str = typer.Option(
            "sk-wave7-secret",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave7_policy_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave7-eval")
    def wave7_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave7_eval(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
