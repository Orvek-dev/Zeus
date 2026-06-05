from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphResult
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionRuntime


def register_wave143_commands(app: typer.Typer) -> None:
    @app.command("live-research-ontology-ingestion")
    def live_research_ontology_ingestion(
        graph_result_json: str = typer.Option(..., "--graph-result-json"),
        candidate_ref: str = typer.Option(..., "--candidate-ref"),
        term: str = typer.Option(..., "--term"),
        definition: str = typer.Option(..., "--definition"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            graph_result = LiveResearchEvidenceGraphResult.model_validate_json(graph_result_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_research_ontology_ingestion",
                    "error": str(exc),
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchOntologyIngestionRuntime().propose(
            graph_result=graph_result,
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
