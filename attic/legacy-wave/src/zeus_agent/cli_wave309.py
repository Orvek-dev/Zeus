from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.stable_release_runtime import build_stable_release_contract


def register_wave309_commands(app: typer.Typer) -> None:
    @app.command("stable-release")
    def stable_release(
        raw_release_note: str = typer.Option("", "--raw-release-note"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_stable_release_contract(raw_release_note=raw_release_note).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
