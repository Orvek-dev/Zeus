from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue

from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime


def register_wave145_commands(app: typer.Typer) -> None:
    @app.command("live-research-ontology-record-delete")
    def live_research_ontology_record_delete(
        record_id: str = typer.Option(..., "--record-id"),
        deletion_ref: str = typer.Option(..., "--deletion-ref"),
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveResearchOntologyRegistryRuntime(home).delete(
            record_id=record_id,
            deletion_ref=deletion_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
