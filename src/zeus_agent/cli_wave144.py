from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionResult
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime


def register_wave144_commands(app: typer.Typer) -> None:
    @app.command("live-research-ontology-record")
    def live_research_ontology_record(
        ingestion_json: str = typer.Option(..., "--ingestion-json"),
        record_ref: str = typer.Option(..., "--record-ref"),
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            ingestion = LiveResearchOntologyIngestionResult.model_validate_json(ingestion_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_research_ontology_record",
                    "error": str(exc),
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchOntologyRegistryRuntime(home).record(
            ingestion=ingestion,
            record_ref=record_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-ontology-records")
    def live_research_ontology_records(
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveResearchOntologyRegistryRuntime(home).list()
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
