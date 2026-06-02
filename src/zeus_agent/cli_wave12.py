from __future__ import annotations

import json
from pathlib import Path

import typer

from zeus_agent.eval.wave12 import Wave12EvalPayload, run_wave12_eval
from zeus_agent.wave12_conversation_scenarios import (
    wave12_conversation_blocks_payload,
    wave12_conversation_happy_payload,
)

Wave12Payload = dict[str, object]


def register_wave12_commands(app: typer.Typer) -> None:
    @app.command("wave12-chat")
    def wave12_chat(
        message: str = typer.Option(..., "--message", help="Conversation message."),
        home: Path = typer.Option(..., "--home", help="State home for Wave12 session lineage."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave12_conversation_happy_payload(message=message, home=home),
            as_json=as_json,
        )

    @app.command("wave12-blocks")
    def wave12_blocks(
        secret_like: str = typer.Option(
            "ghp_TEST_FIXTURE",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave12_conversation_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave12-eval")
    def wave12_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave12_eval(), as_json=as_json)


def _print_payload(payload: Wave12Payload | Wave12EvalPayload, *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
