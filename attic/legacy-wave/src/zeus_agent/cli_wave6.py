from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

import typer

from zeus_agent.eval.wave6 import run_wave6_eval
from zeus_agent.wave6_scenarios import (
    wave6_promotion_controls_payload,
    wave6_runtime_state_payload,
)


def register_wave6_commands(app: typer.Typer) -> None:
    @app.command("wave6-state")
    def wave6_state(
        home: Optional[Path] = typer.Option(None, "--home", help="Local Wave6 state home."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        state_home = home if home is not None else Path(tempfile.mkdtemp(prefix="zeus-wave6-state-"))
        _print_payload(wave6_runtime_state_payload(state_home), as_json=as_json)

    @app.command("wave6-promotion")
    def wave6_promotion(
        home: Optional[Path] = typer.Option(None, "--home", help="Local Wave6 state home."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        state_home = home if home is not None else Path(tempfile.mkdtemp(prefix="zeus-wave6-promotion-"))
        _print_payload(wave6_promotion_controls_payload(state_home), as_json=as_json)

    @app.command("wave6-eval")
    def wave6_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave6_eval(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
