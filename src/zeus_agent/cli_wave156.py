from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigRuntime


def register_wave156_commands(app: typer.Typer) -> None:
    @app.command("live-research-source-config")
    def live_research_source_config(
        adapter_id: str = typer.Option(..., "--adapter-id"),
        endpoint: Optional[str] = typer.Option(None, "--endpoint"),
        allow_loopback_smoke: bool = typer.Option(False, "--allow-loopback-smoke"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveResearchSourceConfigRuntime().configure(
            adapter_id=adapter_id,
            endpoint=endpoint,
            allow_loopback_smoke=allow_loopback_smoke,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
