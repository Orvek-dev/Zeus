from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Union

import typer

from zeus_agent.eval.wave16 import Wave16EvalPayload, run_wave16_eval
from zeus_agent.wave16_provider_live_scenarios import (
    Wave16Payload,
    wave16_provider_live_blocks_payload,
    wave16_provider_live_payload,
)

JsonScalar = Union[str, int, bool, None]
Wave16CliPayload = Mapping[str, Union[JsonScalar, list[dict[str, str]]]]


def register_wave16_commands(app: typer.Typer) -> None:
    @app.command("wave16-provider-live")
    def wave16_provider_live(
        scenario: str = typer.Option(
            "loopback",
            "--scenario",
            help="Wave16 loopback-only live provider HTTP scenario.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        if scenario != "loopback":
            raise typer.BadParameter("scenario must be loopback")
        _print_payload(wave16_provider_live_payload(scenario=scenario), as_json=as_json)

    @app.command("wave16-provider-live-blocks")
    def wave16_provider_live_blocks(
        secret_like: str = typer.Option(
            "redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave16_provider_live_blocks_payload(secret_like), as_json=as_json)

    @app.command("wave16-eval")
    def wave16_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave16_eval(), as_json=as_json)


def _print_payload(
    payload: Wave16Payload | Wave16EvalPayload | Wave16CliPayload,
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
