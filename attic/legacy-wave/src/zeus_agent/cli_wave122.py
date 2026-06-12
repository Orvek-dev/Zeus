from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_provider_direct_adapter_runtime import (
    LiveProviderDirectAdapterReceipt,
    LiveProviderDirectAdapterRuntime,
    StaticProviderDirectAdapterClient,
)
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult


def register_wave122_commands(app: typer.Typer) -> None:
    @app.command("live-provider-direct-adapter")
    def live_provider_direct_adapter(
        claim_json: str = typer.Option(..., "--claim-json"),
        policy_json: str = typer.Option(..., "--policy-json"),
        preflight_json: str = typer.Option(..., "--preflight-json"),
        handoff_json: str = typer.Option(..., "--handoff-json"),
        credential_injection_json: str = typer.Option(..., "--credential-injection-json"),
        provider_envelope_json: str = typer.Option(..., "--provider-envelope-json"),
        client_receipt_json: str = typer.Option(..., "--client-receipt-json"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            claim = LiveProductionClaimResult.model_validate_json(claim_json)
            policy = LiveRemoteTransportPolicyResult.model_validate_json(policy_json)
            preflight = LiveRemoteExecutorPreflightResult.model_validate_json(preflight_json)
            handoff = LiveRemoteCredentialHandoffResult.model_validate_json(handoff_json)
            credential_injection = LiveCredentialInjectionResult.model_validate_json(credential_injection_json)
            provider_envelope = LiveProviderRequestResult.model_validate_json(provider_envelope_json)
            receipt = LiveProviderDirectAdapterReceipt.model_validate_json(client_receipt_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_provider_direct_adapter",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProviderDirectAdapterRuntime().execute(
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            credential_injection=credential_injection,
            provider_envelope=provider_envelope,
            client=StaticProviderDirectAdapterClient(receipt),
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
