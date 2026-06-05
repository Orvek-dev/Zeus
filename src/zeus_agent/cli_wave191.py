from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionResult,
)
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryRuntime,
)


def register_wave191_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-ontology-record")
    def live_research_workflow_ontology_record(
        workflow_ingestion_json: str = typer.Option(..., "--workflow-ingestion-json"),
        record_ref: str = typer.Option(..., "--record-ref"),
        home: Path = typer.Option(..., "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            workflow_ingestion = LiveResearchWorkflowOntologyIngestionResult.model_validate_json(
                workflow_ingestion_json
            )
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_ontology_record"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowOntologyRegistryRuntime(home).record(
            workflow_ingestion=workflow_ingestion,
            record_ref=record_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
