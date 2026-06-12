from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Union

import typer

from zeus_agent.eval.wave15 import run_wave15_eval
from zeus_agent.wave15_live_agent_scenarios import (
    wave15_live_agent_blocks_payload,
    wave15_live_agent_payload,
)

JsonScalar = Union[str, int, bool, None]
JsonValue = Union[JsonScalar, list[dict[str, str]], tuple[str, ...]]
Wave15CliPayload = Mapping[str, JsonValue]


def register_wave15_commands(app: typer.Typer) -> None:
    @app.command("wave15-live-agent")
    def wave15_live_agent(
        scenario: str = typer.Option(
            "tool-loop",
            "--scenario",
            help="Wave15 fake/local live agent scenario.",
        ),
        home: Path = typer.Option(
            Path(".wave15-state"),
            "--home",
            help="Local state home used for Wave15 live agent records.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave15_live_agent_payload(home=home, scenario=scenario),
            as_json=as_json,
        )

    @app.command("wave15-live-agent-blocks")
    def wave15_live_agent_blocks(
        secret_like: str = typer.Option(
            "redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        home: Path = typer.Option(
            Path(".wave15-state"),
            "--home",
            help="Local state home used for Wave15 live agent block records.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave15_live_agent_blocks_payload(home=home, raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave15-eval")
    def wave15_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave15_eval(), as_json=as_json)


def _print_payload(payload: Wave15CliPayload, *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
