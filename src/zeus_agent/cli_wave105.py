from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_delivery_adapter_runtime.models import LiveGatewayDeliveryAdapterResult
from zeus_agent.live_gateway_http_transport_runtime import LiveGatewayHttpTransportResult
from zeus_agent.live_gateway_external_transport_runtime import LiveGatewayExternalTransportResult
from zeus_agent.live_gateway_owned_client_transport_runtime import LiveGatewayOwnedClientTransportResult
from zeus_agent.live_gateway_loopback_transport_runtime import LiveGatewayLoopbackTransportResult
from zeus_agent.live_mcp_http_transport_runtime import LiveMcpHttpTransportResult
from zeus_agent.live_mcp_external_transport_runtime import LiveMcpExternalTransportResult
from zeus_agent.live_mcp_remote_adapter_runtime.models import LiveMcpRemoteAdapterResult
from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientTransportResult
from zeus_agent.live_mcp_loopback_transport_runtime import LiveMcpLoopbackTransportResult
from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalTransportResult
from zeus_agent.live_provider_direct_adapter_runtime.models import LiveProviderDirectAdapterResult
from zeus_agent.live_provider_owned_client_transport_runtime import LiveProviderOwnedClientTransportResult
from zeus_agent.live_provider_http_transport_runtime import LiveProviderHttpTransportResult
from zeus_agent.live_provider_loopback_transport_runtime import LiveProviderLoopbackTransportResult
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_audit_runtime.runtime import LiveTransportExecutionResult


def register_wave105_commands(app: typer.Typer) -> None:
    @app.command("live-transport-audit")
    def live_transport_audit(
        adapter_kind: str = typer.Option(..., "--adapter-kind"),
        execution_json: str = typer.Option(..., "--execution-json"),
        audit_ref: str = typer.Option(..., "--audit-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            execution = _execution_result(adapter_kind=adapter_kind, execution_json=execution_json)
        except (JSONDecodeError, ValidationError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_transport_audit",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveTransportAuditRuntime().audit(
            adapter_kind=adapter_kind,
            execution=execution,
            audit_ref=audit_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _execution_result(
    *, adapter_kind: str, execution_json: str
) -> Optional[LiveTransportExecutionResult]:
    if adapter_kind == "provider":
        payload = json.loads(execution_json)
        if isinstance(payload, dict) and payload.get("provider_direct_adapter") is True:
            return LiveProviderDirectAdapterResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("provider_owned_client") is True:
            return LiveProviderOwnedClientTransportResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("transport_kind") == "external_http":
            return LiveProviderExternalTransportResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("transport_kind") == "local_http":
            return LiveProviderHttpTransportResult.model_validate(payload)
        return LiveProviderLoopbackTransportResult.model_validate_json(execution_json)
    if adapter_kind == "gateway":
        payload = json.loads(execution_json)
        if isinstance(payload, dict) and payload.get("gateway_delivery_adapter") is True:
            return LiveGatewayDeliveryAdapterResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("gateway_owned_client") is True:
            return LiveGatewayOwnedClientTransportResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("transport_kind") == "external_http":
            return LiveGatewayExternalTransportResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("transport_kind") == "local_http":
            return LiveGatewayHttpTransportResult.model_validate(payload)
        return LiveGatewayLoopbackTransportResult.model_validate_json(execution_json)
    if adapter_kind == "mcp":
        payload = json.loads(execution_json)
        if isinstance(payload, dict) and payload.get("mcp_remote_adapter") is True:
            return LiveMcpRemoteAdapterResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("mcp_owned_client") is True:
            return LiveMcpOwnedClientTransportResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("transport_kind") == "remote_server":
            return LiveMcpExternalTransportResult.model_validate(payload)
        if isinstance(payload, dict) and payload.get("transport_kind") == "local_http":
            return LiveMcpHttpTransportResult.model_validate(payload)
        return LiveMcpLoopbackTransportResult.model_validate_json(execution_json)
    return None


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
