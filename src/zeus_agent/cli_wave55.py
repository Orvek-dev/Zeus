from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.research_cockpit_runtime import ResearchCockpitRuntime


def register_wave55_commands(app: typer.Typer) -> None:
    @app.command("research")
    def research(
        source_id: Optional[str] = typer.Option(None, "--source"),
        query: str = typer.Option("agent workflow research", "--query"),
        objective_id: str = typer.Option("wave55.research", "--objective-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = ResearchCockpitRuntime().build(
            source_id=source_id,
            query=query,
            objective_id=objective_id,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
