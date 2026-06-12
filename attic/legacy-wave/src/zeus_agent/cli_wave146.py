from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_evidence_graph_runtime import LiveResearchEvidenceGraphResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportResult
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeResult
from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionResult
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryResult
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientTransportResult
from zeus_agent.live_research_status_runtime import LiveResearchStatusRuntime


def register_wave146_commands(app: typer.Typer) -> None:
    @app.command("live-research-status")
    def live_research_status(
        policy_json: str = typer.Option(..., "--policy-json"),
        external_result_json: Optional[str] = typer.Option(None, "--external-result-json"),
        owned_client_result_json: Optional[str] = typer.Option(None, "--owned-client-result-json"),
        loopback_smoke_result_json: Optional[str] = typer.Option(None, "--loopback-smoke-result-json"),
        graph_result_json: Optional[str] = typer.Option(None, "--graph-result-json"),
        ingestion_json: Optional[str] = typer.Option(None, "--ingestion-json"),
        registry_record_json: Optional[str] = typer.Option(None, "--registry-record-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            policy = LiveResearchActivationPolicyResult.model_validate_json(policy_json)
            external_result = _external_result(external_result_json)
            owned_client_result = _owned_client_result(owned_client_result_json)
            loopback_smoke_result = _loopback_smoke_result(loopback_smoke_result_json)
            graph_result = _graph_result(graph_result_json)
            ingestion = _ingestion(ingestion_json)
            registry_record = _registry_record(registry_record_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_research_status",
                    "error": str(exc),
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchStatusRuntime().build(
            policy=policy,
            external_result=external_result,
            owned_client_result=owned_client_result,
            loopback_smoke_result=loopback_smoke_result,
            graph_result=graph_result,
            ingestion=ingestion,
            registry_record=registry_record,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _external_result(raw: Optional[str]) -> Optional[LiveResearchExternalTransportResult]:
    if raw is None:
        return None
    return LiveResearchExternalTransportResult.model_validate_json(raw)


def _owned_client_result(raw: Optional[str]) -> Optional[LiveResearchOwnedClientTransportResult]:
    if raw is None:
        return None
    return LiveResearchOwnedClientTransportResult.model_validate_json(raw)


def _loopback_smoke_result(raw: Optional[str]) -> Optional[LiveResearchLoopbackSmokeResult]:
    if raw is None:
        return None
    return LiveResearchLoopbackSmokeResult.model_validate_json(raw)


def _graph_result(raw: Optional[str]) -> Optional[LiveResearchEvidenceGraphResult]:
    if raw is None:
        return None
    return LiveResearchEvidenceGraphResult.model_validate_json(raw)


def _ingestion(raw: Optional[str]) -> Optional[LiveResearchOntologyIngestionResult]:
    if raw is None:
        return None
    return LiveResearchOntologyIngestionResult.model_validate_json(raw)


def _registry_record(raw: Optional[str]) -> Optional[LiveResearchOntologyRegistryResult]:
    if raw is None:
        return None
    return LiveResearchOntologyRegistryResult.model_validate_json(raw)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
