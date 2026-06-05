from __future__ import annotations

import json
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.live_execution_bundle_runtime.models import LiveExecutionSurfaceSummary
from zeus_agent.live_gateway_credentialed_http_runtime import LiveGatewayCredentialedHttpResult
from zeus_agent.live_mcp_credentialed_http_runtime import LiveMcpCredentialedHttpResult
from zeus_agent.live_provider_credentialed_http_runtime import LiveProviderCredentialedHttpResult

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


def surface_summaries(
    provider_result: Optional[LiveProviderCredentialedHttpResult],
    gateway_result: Optional[LiveGatewayCredentialedHttpResult],
    mcp_result: Optional[LiveMcpCredentialedHttpResult],
) -> tuple[LiveExecutionSurfaceSummary, ...]:
    return tuple(
        summary
        for summary in (
            _provider_summary(provider_result),
            _gateway_summary(gateway_result),
            _mcp_summary(mcp_result),
        )
        if summary is not None
    )


def source_secret_reasons(
    provider_result: Optional[LiveProviderCredentialedHttpResult],
    gateway_result: Optional[LiveGatewayCredentialedHttpResult],
    mcp_result: Optional[LiveMcpCredentialedHttpResult],
) -> tuple[str, ...]:
    checks = (
        ("provider", provider_result),
        ("gateway", gateway_result),
        ("mcp", mcp_result),
    )
    return tuple(
        "{0}:secret_echo_detected".format(kind)
        for kind, result in checks
        if result is not None and _contains_secret_marker(result.to_payload())
    )


def surface_reasons(surface: LiveExecutionSurfaceSummary) -> tuple[str, ...]:
    reasons = ["{0}:{1}".format(surface.surface_kind, reason) for reason in surface.blocked_reasons]
    if surface.decision != "executed":
        reasons.append("{0}:execution_not_executed".format(surface.surface_kind))
    if not surface.local_http_loopback:
        reasons.append("{0}:loopback_proof_required".format(surface.surface_kind))
    if surface.non_loopback_network_opened:
        reasons.append("{0}:non_loopback_network_opened".format(surface.surface_kind))
    if surface.external_delivery_opened:
        reasons.append("{0}:external_delivery_opened".format(surface.surface_kind))
    if surface.raw_secret_returned:
        reasons.append("{0}:raw_secret_returned".format(surface.surface_kind))
    if not surface.no_secret_echo:
        reasons.append("{0}:secret_echo_detected".format(surface.surface_kind))
    if surface.live_production_claimed:
        reasons.append("{0}:live_production_claimed".format(surface.surface_kind))
    return tuple(reasons)


def _provider_summary(
    result: Optional[LiveProviderCredentialedHttpResult],
) -> Optional[LiveExecutionSurfaceSummary]:
    if result is None:
        return None
    return LiveExecutionSurfaceSummary(
        surface_kind="provider",
        decision=result.decision,
        execution_id=result.execution_id,
        release_id=result.release_id,
        body_id=result.body_id,
        endpoint_host=result.transport_endpoint_host,
        execution_ref=result.execution_ref,
        cleanup_receipt=result.cleanup_receipt,
        blocked_reasons=result.blocked_reasons,
        status_code=result.status_code,
        local_http_loopback=result.local_http_loopback,
        credentialed_http=result.provider_credentialed_http,
        sealed_credential_bound=result.sealed_credential_bound,
        material_released_to_consumer=result.material_released_to_consumer,
        network_opened=result.network_opened,
        non_loopback_network_opened=result.non_loopback_network_opened,
        handler_executed=result.handler_executed,
        external_delivery_opened=result.external_delivery_opened,
        credential_material_accessed=result.credential_material_accessed,
        raw_secret_returned=result.raw_secret_returned,
        no_secret_echo=result.no_secret_echo,
        live_production_claimed=result.live_production_claimed,
    )


def _gateway_summary(
    result: Optional[LiveGatewayCredentialedHttpResult],
) -> Optional[LiveExecutionSurfaceSummary]:
    if result is None:
        return None
    return LiveExecutionSurfaceSummary(
        surface_kind="gateway",
        decision=result.decision,
        execution_id=result.execution_id,
        release_id=result.release_id,
        body_id=result.body_id,
        endpoint_host=result.delivery_endpoint_host,
        execution_ref=result.execution_ref,
        cleanup_receipt=result.cleanup_receipt,
        blocked_reasons=result.blocked_reasons,
        status_code=result.status_code,
        local_http_loopback=result.local_http_loopback,
        credentialed_http=result.gateway_credentialed_http,
        sealed_credential_bound=result.sealed_credential_bound,
        material_released_to_consumer=result.material_released_to_consumer,
        network_opened=result.network_opened,
        non_loopback_network_opened=result.non_loopback_network_opened,
        handler_executed=result.handler_executed,
        external_delivery_opened=result.external_delivery_opened,
        credential_material_accessed=result.credential_material_accessed,
        raw_secret_returned=result.raw_secret_returned,
        no_secret_echo=result.no_secret_echo,
        live_production_claimed=result.live_production_claimed,
    )


def _mcp_summary(result: Optional[LiveMcpCredentialedHttpResult]) -> Optional[LiveExecutionSurfaceSummary]:
    if result is None:
        return None
    return LiveExecutionSurfaceSummary(
        surface_kind="mcp",
        decision=result.decision,
        execution_id=result.execution_id,
        release_id=result.release_id,
        body_id=result.body_id,
        endpoint_host=result.transport_endpoint_host,
        execution_ref=result.execution_ref,
        cleanup_receipt=result.cleanup_receipt,
        blocked_reasons=result.blocked_reasons,
        status_code=result.status_code,
        local_http_loopback=result.local_http_loopback,
        credentialed_http=result.mcp_credentialed_http,
        sealed_credential_bound=result.sealed_credential_bound,
        material_released_to_consumer=result.material_released_to_consumer,
        network_opened=result.network_opened,
        non_loopback_network_opened=result.non_loopback_network_opened,
        handler_executed=result.handler_executed,
        external_delivery_opened=result.external_delivery_opened,
        credential_material_accessed=result.credential_material_accessed,
        raw_secret_returned=result.raw_secret_returned,
        no_secret_echo=result.no_secret_echo,
        live_production_claimed=result.live_production_claimed,
    )


def _contains_secret_marker(payload: dict[str, JsonValue]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    return any(marker in serialized for marker in _SECRET_MARKERS)
