from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_delivery_adapter_runtime import (
    LiveGatewayDeliveryAdapterReceipt,
    LiveGatewayDeliveryAdapterRuntime,
    StaticGatewayDeliveryAdapterClient,
)
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult


def register_wave123_commands(app: typer.Typer) -> None:
    @app.command("live-gateway-delivery-adapter")
    def live_gateway_delivery_adapter(
        claim_json: str = typer.Option(..., "--claim-json"),
        policy_json: str = typer.Option(..., "--policy-json"),
        preflight_json: str = typer.Option(..., "--preflight-json"),
        handoff_json: str = typer.Option(..., "--handoff-json"),
        credential_injection_json: str = typer.Option(..., "--credential-injection-json"),
        gateway_envelope_json: str = typer.Option(..., "--gateway-envelope-json"),
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
            gateway_envelope = LiveGatewayDeliveryResult.model_validate_json(gateway_envelope_json)
            receipt = LiveGatewayDeliveryAdapterReceipt.model_validate_json(client_receipt_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_gateway_delivery_adapter",
                    "error": str(exc),
                    "network_opened": False,
                    "external_delivery_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveGatewayDeliveryAdapterRuntime().execute(
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            credential_injection=credential_injection,
            gateway_envelope=gateway_envelope,
            client=StaticGatewayDeliveryAdapterClient(receipt),
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
