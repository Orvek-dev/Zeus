from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Union

import typer

from zeus_agent.eval.wave18 import Wave18EvalPayload, run_wave18_eval
from zeus_agent.wave18_tool_sandbox_scenarios import (
    Wave18Payload,
    wave18_tool_sandbox_blocks_payload,
    wave18_tool_sandbox_payload,
)

JsonScalar = Union[str, int, bool, None]
Wave18CliPayload = Mapping[str, Union[JsonScalar, list[dict[str, str]]]]


def register_wave18_commands(app: typer.Typer) -> None:
    @app.command("wave18-tool-sandbox")
    def wave18_tool_sandbox(
        scenario: str = typer.Option(
            "local-safe",
            "--scenario",
            help="Wave18 controlled local tool sandbox scenario.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        if scenario != "local-safe":
            raise typer.BadParameter("scenario must be local-safe")
        _print_payload(wave18_tool_sandbox_payload(scenario=scenario), as_json=as_json)

    @app.command("wave18-tool-sandbox-blocks")
    def wave18_tool_sandbox_blocks(
        secret_like: str = typer.Option(
            "redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave18_tool_sandbox_blocks_payload(raw_secret=secret_like), as_json=as_json)

    @app.command("wave18-eval")
    def wave18_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave18_eval(), as_json=as_json)


def _print_payload(
    payload: Wave18Payload | Wave18EvalPayload | Wave18CliPayload,
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
