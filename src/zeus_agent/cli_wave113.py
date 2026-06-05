from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_provider_external_transport_runtime import (
    LiveProviderExternalClientResult,
    LiveProviderExternalTransportRuntime,
)
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult


def register_wave113_commands(app: typer.Typer) -> None:
    @app.command("live-provider-external-transport")
    def live_provider_external_transport(
        policy_json: str = typer.Option(..., "--policy-json"),
        preflight_json: str = typer.Option(..., "--preflight-json"),
        provider_envelope_json: str = typer.Option(..., "--provider-envelope-json"),
        client_result_json: str = typer.Option(..., "--client-result-json"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            policy = LiveRemoteTransportPolicyResult.model_validate_json(policy_json)
            preflight = LiveRemoteExecutorPreflightResult.model_validate_json(preflight_json)
            provider_envelope = LiveProviderRequestResult.model_validate_json(provider_envelope_json)
            client_result = LiveProviderExternalClientResult.model_validate_json(client_result_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_provider_external_transport",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProviderExternalTransportRuntime().execute(
            policy=policy,
            preflight=preflight,
            provider_envelope=provider_envelope,
            client_result=client_result,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
