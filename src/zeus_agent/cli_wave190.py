from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_workflow_evidence_graph_runtime import (
    LiveResearchWorkflowEvidenceGraphResult,
)
from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionRuntime,
)


def register_wave190_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-ontology-ingestion")
    def live_research_workflow_ontology_ingestion(
        workflow_graph_json: str = typer.Option(..., "--workflow-graph-json"),
        candidate_ref: str = typer.Option(..., "--candidate-ref"),
        term: str = typer.Option(..., "--term"),
        definition: str = typer.Option(..., "--definition"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            workflow_graph = LiveResearchWorkflowEvidenceGraphResult.model_validate_json(workflow_graph_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_ontology_ingestion"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowOntologyIngestionRuntime().propose(
            workflow_graph=workflow_graph,
            candidate_ref=candidate_ref,
            term=term,
            definition=definition,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
