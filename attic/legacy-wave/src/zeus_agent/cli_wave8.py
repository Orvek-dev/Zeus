from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

import typer

from zeus_agent.eval.wave8 import run_wave8_eval
from zeus_agent.wave8_scenarios import (
    wave8_runtime_integration_payload,
    wave8_transport_state_payload,
)


def register_wave8_commands(app: typer.Typer) -> None:
    @app.command("wave8-state")
    def wave8_state(
        home: Optional[Path] = typer.Option(None, "--home", help="Local Wave8 state home."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        state_home = home if home is not None else Path(tempfile.mkdtemp(prefix="zeus-wave8-state-"))
        _print_payload(wave8_transport_state_payload(state_home), as_json=as_json)

    @app.command("wave8-runtime")
    def wave8_runtime(
        secret_like: str = typer.Option(
            "sk-wave8-secret",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            wave8_runtime_integration_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("wave8-eval")
    def wave8_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave8_eval(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
