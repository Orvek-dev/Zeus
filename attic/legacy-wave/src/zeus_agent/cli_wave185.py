from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionRuntime,
)
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightResult,
)


def register_wave185_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-external-execution")
    def live_research_workflow_external_execution(
        preflight_json: str = typer.Option(..., "--preflight-json"),
        external_result_json: Optional[str] = typer.Option(None, "--external-result-json"),
        owned_client_result_json: Optional[str] = typer.Option(None, "--owned-client-result-json"),
        execution_record_ref: str = typer.Option(..., "--execution-record-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            preflight = LiveResearchWorkflowExternalPreflightResult.model_validate_json(preflight_json)
            external_result = (
                None
                if external_result_json is None
                else LiveResearchExternalTransportResult.model_validate_json(external_result_json)
            )
            owned_client_result = (
                None
                if owned_client_result_json is None
                else LiveResearchOwnedClientTransportResult.model_validate_json(
                    owned_client_result_json
                )
            )
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_external_execution"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowExternalExecutionRuntime().record(
            preflight=preflight,
            external_result=external_result,
            owned_client_result=owned_client_result,
            execution_record_ref=execution_record_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
