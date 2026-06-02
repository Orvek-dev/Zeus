from __future__ import annotations

import json

import typer

from zeus_agent.eval.total_architecture import run_total_architecture_eval
from zeus_agent.total_runtime import (
    total_architecture_blocks_payload,
    total_architecture_plan_payload,
)


def register_total_commands(app: typer.Typer) -> None:
    @app.command("total-plan")
    def total_plan(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(total_architecture_plan_payload(), as_json=as_json)

    @app.command("total-blocks")
    def total_blocks(
        secret_like: str = typer.Option(
            "ghp_TEST_FIXTURE",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            total_architecture_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("total-eval")
    def total_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_total_architecture_eval(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
