from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Union

import typer

from zeus_agent.eval.wave19 import Wave19EvalPayload, run_wave19_eval
from zeus_agent.wave19_research_provider_scenarios import (
    Wave19Payload,
    wave19_research_provider_blocks_payload,
    wave19_research_provider_payload,
)

JsonScalar = Union[str, int, bool, None]
Wave19CliPayload = Mapping[str, Union[JsonScalar, list[dict[str, str]], list[str]]]


def register_wave19_commands(app: typer.Typer) -> None:
    @app.command("wave19-research-provider")
    def wave19_research_provider(
        scenario: str = typer.Option(
            "pinned-fake",
            "--scenario",
            help="Wave19 fake web/GitHub research provider scenario.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        if scenario != "pinned-fake":
            raise typer.BadParameter("scenario must be pinned-fake")
        _print_payload(wave19_research_provider_payload(scenario=scenario), as_json=as_json)

    @app.command("wave19-research-provider-blocks")
    def wave19_research_provider_blocks(
        secret_like: str = typer.Option(
            "redaction-sentinel",
            "--secret-like",
            help="Sample value used to exercise redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(wave19_research_provider_blocks_payload(raw_secret=secret_like), as_json=as_json)

    @app.command("wave19-eval")
    def wave19_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave19_eval(), as_json=as_json)


def _print_payload(
    payload: Wave19Payload | Wave19EvalPayload | Wave19CliPayload,
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
