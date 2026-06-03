from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Union

import typer

from zeus_agent.eval.wave14 import run_wave14_eval
from zeus_agent.wave14_live_connection_scenarios import (
    wave14_live_blocks_payload,
    wave14_live_plan_payload,
)
from zeus_agent.wave14_orchestra_scenarios import wave14_orchestra_plan_payload

JsonScalar = Union[str, int, bool, None]
JsonValue = Union[JsonScalar, list[JsonScalar], Mapping[str, JsonScalar]]
Wave14CliPayload = Mapping[str, JsonValue]


def register_wave14_commands(app: typer.Typer) -> None:
    @app.command("wave14-live-plan")
    def wave14_live_plan(
        scenario: str = typer.Option(
            "full-dry-run",
            "--scenario",
            help="Wave14 live connection planning scenario.",
        ),
        home: Path = typer.Option(
            Path(".wave14-state"),
            "--home",
            help="Local state home used for Wave14 live connection records.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave14_live_plan_payload(home=home, scenario=scenario),
            as_json=as_json,
        )

    @app.command("wave14-live-blocks")
    def wave14_live_blocks(
        secret_like: str = typer.Option(
            "redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        home: Path = typer.Option(
            Path(".wave14-state"),
            "--home",
            help="Local state home used for Wave14 live connection block records.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave14_live_blocks_payload(home=home, raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave14-orchestra-plan")
    def wave14_orchestra_plan(
        scenario: str = typer.Option(
            "parallel-dry-run",
            "--scenario",
            help="Wave14 orchestra planning scenario.",
        ),
        home: Path = typer.Option(
            Path(".wave14-state"),
            "--home",
            help="Local state home used for Wave14 orchestra records.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave14_orchestra_plan_payload(home=home, scenario=scenario),
            as_json=as_json,
        )

    @app.command("wave14-eval")
    def wave14_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave14_eval(), as_json=as_json)


def _print_payload(payload: Wave14CliPayload, *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
