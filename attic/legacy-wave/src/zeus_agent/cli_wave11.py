from __future__ import annotations

import json

import typer

from zeus_agent.eval.wave11 import Wave11EvalPayload, run_wave11_eval
from zeus_agent.wave11_tool_scenarios import (
    wave11_tool_mcp_blocks_payload,
    wave11_tool_mcp_happy_payload,
)

Wave11Payload = dict[str, object]


def register_wave11_commands(app: typer.Typer) -> None:
    @app.command("wave11-tools")
    def wave11_tools(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave11_tool_mcp_happy_payload(), as_json=as_json)

    @app.command("wave11-blocks")
    def wave11_blocks(
        secret_like: str = typer.Option(
            "ghp_TEST_FIXTURE",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave11_tool_mcp_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave11-eval")
    def wave11_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave11_eval(), as_json=as_json)


def _print_payload(
    payload: Wave11Payload | Wave11EvalPayload,
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
