from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_mcp_remote_adapter_runtime import (
    LiveMcpRemoteAdapterReceipt,
    LiveMcpRemoteAdapterRuntime,
    StaticMcpRemoteAdapterClient,
)
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult


def register_wave124_commands(app: typer.Typer) -> None:
    @app.command("live-mcp-remote-adapter")
    def live_mcp_remote_adapter(
        claim_json: str = typer.Option(..., "--claim-json"),
        policy_json: str = typer.Option(..., "--policy-json"),
        preflight_json: str = typer.Option(..., "--preflight-json"),
        handoff_json: str = typer.Option(..., "--handoff-json"),
        credential_injection_json: str = typer.Option(..., "--credential-injection-json"),
        mcp_envelope_json: str = typer.Option(..., "--mcp-envelope-json"),
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
            mcp_envelope = LiveMcpRequestResult.model_validate_json(mcp_envelope_json)
            receipt = LiveMcpRemoteAdapterReceipt.model_validate_json(client_receipt_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_mcp_remote_adapter",
                    "error": str(exc),
                    "network_opened": False,
                    "server_started": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveMcpRemoteAdapterRuntime().execute(
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            credential_injection=credential_injection,
            mcp_envelope=mcp_envelope,
            client=StaticMcpRemoteAdapterClient(receipt),
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
