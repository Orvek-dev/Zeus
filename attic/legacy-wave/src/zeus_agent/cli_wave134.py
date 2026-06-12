from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleRuntime
from zeus_agent.live_gateway_credentialed_http_runtime import LiveGatewayCredentialedHttpResult
from zeus_agent.live_mcp_credentialed_http_runtime import LiveMcpCredentialedHttpResult
from zeus_agent.live_provider_credentialed_http_runtime import LiveProviderCredentialedHttpResult


def register_wave134_commands(app: typer.Typer) -> None:
    @app.command("live-execution-bundle")
    def live_execution_bundle(
        provider_result_json: Optional[str] = typer.Option(None, "--provider-result-json"),
        gateway_result_json: Optional[str] = typer.Option(None, "--gateway-result-json"),
        mcp_result_json: Optional[str] = typer.Option(None, "--mcp-result-json"),
        bundle_ref: str = typer.Option(..., "--bundle-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            provider_result = _provider(provider_result_json)
            gateway_result = _gateway(gateway_result_json)
            mcp_result = _mcp(mcp_result_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execution_bundle",
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "raw_secret_returned": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveExecutionBundleRuntime().summarize(
            provider_result=provider_result,
            gateway_result=gateway_result,
            mcp_result=mcp_result,
            bundle_ref=bundle_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _provider(raw: Optional[str]) -> Optional[LiveProviderCredentialedHttpResult]:
    if raw is None:
        return None
    return LiveProviderCredentialedHttpResult.model_validate_json(raw)


def _gateway(raw: Optional[str]) -> Optional[LiveGatewayCredentialedHttpResult]:
    if raw is None:
        return None
    return LiveGatewayCredentialedHttpResult.model_validate_json(raw)


def _mcp(raw: Optional[str]) -> Optional[LiveMcpCredentialedHttpResult]:
    if raw is None:
        return None
    return LiveMcpCredentialedHttpResult.model_validate_json(raw)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
