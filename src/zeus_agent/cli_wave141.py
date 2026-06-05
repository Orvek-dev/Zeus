from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_external_transport_runtime import (
    LiveResearchExternalClientResult,
    LiveResearchExternalTransportRuntime,
)


def register_wave141_commands(app: typer.Typer) -> None:
    @app.command("live-research-external-transport")
    def live_research_external_transport(
        policy_json: str = typer.Option(..., "--policy-json"),
        client_result_json: str = typer.Option(..., "--client-result-json"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            policy = LiveResearchActivationPolicyResult.model_validate_json(policy_json)
            client_result = LiveResearchExternalClientResult.model_validate_json(client_result_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_research_external_transport",
                    "error": str(exc),
                    "network_opened": False,
                    "live_search_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchExternalTransportRuntime().execute(
            policy=policy,
            client_result=client_result,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
