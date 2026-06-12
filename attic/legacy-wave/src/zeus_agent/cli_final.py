from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

import typer

from zeus_agent.eval.final_architecture import run_final_architecture_eval
from zeus_agent.product_runtime import (
    final_adversarial_blocks_payload,
    final_core_contracts_payload,
    final_state_persistence_payload,
)


def register_final_commands(app: typer.Typer) -> None:
    @app.command("final-core")
    def final_core(
        objective: str = typer.Option(
            "Implement final Zeus architecture with governed dry-run runtime.",
            "--objective",
            help="Flexible objective to compile into a governed Zeus product snapshot.",
        ),
        secret_like: str = typer.Option(
            "ghp_TEST_FIXTURE",
            "--secret-like",
            help="Secret-like sample used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            final_core_contracts_payload(objective=objective, raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("final-adversarial")
    def final_adversarial(
        secret_like: str = typer.Option(
            "sk-final-adversarial-secret",
            "--secret-like",
            help="Secret-like sample used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(
            final_adversarial_blocks_payload(raw_secret=secret_like),
            as_json=as_json,
        )

    @app.command("final-eval")
    def final_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_final_architecture_eval(), as_json=as_json)

    @app.command("final-state")
    def final_state(
        home: Optional[Path] = typer.Option(None, "--home", help="Local final product state home."),
        secret_like: str = typer.Option(
            "ghp_TEST_FIXTURE",
            "--secret-like",
            help="Secret-like sample used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        state_home = home if home is not None else Path(tempfile.mkdtemp(prefix="zeus-final-state-"))
        _print_payload(
            final_state_persistence_payload(home=state_home, raw_secret=secret_like),
            as_json=as_json,
        )


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
