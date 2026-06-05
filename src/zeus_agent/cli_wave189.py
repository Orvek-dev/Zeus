from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_workflow_evidence_graph_runtime import (
    LiveResearchWorkflowEvidenceGraphRuntime,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
)


def register_wave189_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-evidence-graph")
    def live_research_workflow_evidence_graph(
        workflow_external_execution_json: str = typer.Option(..., "--workflow-external-execution-json"),
        external_result_json: str = typer.Option(..., "--external-result-json"),
        graph_ref: str = typer.Option(..., "--graph-ref"),
        objective_id: str = typer.Option(..., "--objective-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            workflow_external_execution = LiveResearchWorkflowExternalExecutionResult.model_validate_json(
                workflow_external_execution_json
            )
            external_result = LiveResearchExternalTransportResult.model_validate_json(external_result_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_evidence_graph"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowEvidenceGraphRuntime().build(
            workflow_external_execution=workflow_external_execution,
            external_result=external_result,
            graph_ref=graph_ref,
            objective_id=objective_id,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
