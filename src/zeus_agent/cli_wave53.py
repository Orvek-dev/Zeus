from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.ontology_cockpit_runtime import OntologyCockpitRuntime


def register_wave53_commands(app: typer.Typer) -> None:
    @app.command("ontology")
    def ontology(
        home: Optional[Path] = typer.Option(None, "--home"),
        candidate_id: Optional[str] = typer.Option(None, "--candidate-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = OntologyCockpitRuntime(home or default_zeus_home()).build(candidate_id=candidate_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
