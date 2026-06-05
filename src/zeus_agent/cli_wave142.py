from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphRuntime
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult


def register_wave142_commands(app: typer.Typer) -> None:
    @app.command("live-research-evidence-graph")
    def live_research_evidence_graph(
        external_result_json: Optional[str] = typer.Option(None, "--external-result-json"),
        owned_client_result_json: Optional[str] = typer.Option(None, "--owned-client-result-json"),
        graph_ref: str = typer.Option(..., "--graph-ref"),
        objective_id: str = typer.Option(..., "--objective-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            external_result = (
                None
                if external_result_json is None
                else LiveResearchExternalTransportResult.model_validate_json(external_result_json)
            )
            owned_client_result = (
                None
                if owned_client_result_json is None
                else LiveResearchOwnedClientTransportResult.model_validate_json(owned_client_result_json)
            )
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_research_evidence_graph",
                    "error": str(exc),
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchEvidenceGraphRuntime().build(
            external_result=external_result,
            owned_client_result=owned_client_result,
            graph_ref=graph_ref,
            objective_id=objective_id,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
