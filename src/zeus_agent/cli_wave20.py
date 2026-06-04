from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Union

import typer

from zeus_agent.eval.wave20 import Wave20EvalPayload, run_wave20_eval
from zeus_agent.wave20_observability_scenarios import (
    Wave20Payload,
    wave20_observability_blocks_payload,
    wave20_observability_payload,
)

JsonScalar = Union[str, int, bool, None]
Wave20CliPayload = Mapping[str, Union[JsonScalar, list[dict[str, str]]]]


def register_wave20_commands(app: typer.Typer) -> None:
    @app.command("wave20-observability-gates")
    def wave20_observability_gates(
        scenario: str = typer.Option(
            "happy",
            "--scenario",
            help="Wave20 observability/security gate scenario.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        if scenario != "happy":
            raise typer.BadParameter("scenario must be happy")
        _print_payload(wave20_observability_payload(), as_json=as_json)

    @app.command("wave20-observability-gates-blocks")
    def wave20_observability_gates_blocks(
        secret_like: str = typer.Option(
            "sk-wave20-default-redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        if secret_like.strip() == "":
            raise typer.BadParameter("secret-like must be non-empty")
        _print_payload(
            wave20_observability_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave20-eval")
    def wave20_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave20_eval(), as_json=as_json)


def _print_payload(
    payload: Wave20Payload | Wave20EvalPayload | Wave20CliPayload,
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
