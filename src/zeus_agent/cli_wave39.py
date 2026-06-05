from __future__ import annotations

import json

import typer

from zeus_agent.live_readiness_runtime import LiveReadinessRuntime


def register_wave39_commands(app: typer.Typer) -> None:
    @app.command("live-readiness")
    def live_readiness(as_json: bool = typer.Option(False, "--json")) -> None:
        report = LiveReadinessRuntime().build_report()
        _print_payload(report.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
