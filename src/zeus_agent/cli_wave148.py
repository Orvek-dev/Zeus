from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_owned_client_transport_runtime import (
    LiveResearchOwnedClientReceipt,
    LiveResearchOwnedClientTransportRuntime,
    StaticResearchOwnedClient,
)


def register_wave148_commands(app: typer.Typer) -> None:
    @app.command("live-research-owned-client-transport")
    def live_research_owned_client_transport(
        policy_json: str = typer.Option(..., "--policy-json"),
        client_receipt_json: str = typer.Option(..., "--client-receipt-json"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            policy = LiveResearchActivationPolicyResult.model_validate_json(policy_json)
            receipt = LiveResearchOwnedClientReceipt.model_validate_json(client_receipt_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_research_owned_client_transport",
                    "error": str(exc),
                    "network_opened": False,
                    "live_search_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchOwnedClientTransportRuntime().execute(
            policy=policy,
            client=StaticResearchOwnedClient(receipt),
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
