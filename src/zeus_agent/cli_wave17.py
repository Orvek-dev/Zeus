from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Union

import typer

from zeus_agent.eval.wave17 import Wave17EvalPayload, run_wave17_eval
from zeus_agent.wave17_mcp_manager_scenarios import (
    Wave17Payload,
    wave17_mcp_manager_blocks_payload,
    wave17_mcp_manager_payload,
)

JsonScalar = Union[str, int, bool, None]
Wave17CliPayload = Mapping[str, Union[JsonScalar, list[dict[str, str]], list[str]]]


def register_wave17_commands(app: typer.Typer) -> None:
    @app.command("wave17-mcp-manager")
    def wave17_mcp_manager(
        scenario: str = typer.Option(
            "stdio-http",
            "--scenario",
            help="Wave17 fake stdio/http MCP manager scenario.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave17_mcp_manager_payload(scenario=scenario), as_json=as_json)

    @app.command("wave17-mcp-manager-blocks")
    def wave17_mcp_manager_blocks(
        secret_like: str = typer.Option(
            "redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave17_mcp_manager_blocks_payload(raw_secret=secret_like), as_json=as_json)

    @app.command("wave17-eval")
    def wave17_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave17_eval(), as_json=as_json)


def _print_payload(
    payload: Wave17Payload | Wave17EvalPayload | Wave17CliPayload,
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
