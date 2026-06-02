from __future__ import annotations

from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderUsage,
)
from zeus_agent.model_runtime.provider_boundary import (
    ProviderBoundaryRequest,
    ProviderBoundaryResult,
)


def blocked_provider_response(
    request: ProviderRuntimeRequest,
    reason: str,
    *,
    redacted_input: str | None = None,
    fallback_provider_kind: str | None = None,
) -> ProviderRuntimeResponse:
    metadata = [ProviderMetadataEntry(key="block.reason", value=reason)]
    if redacted_input is not None:
        metadata.append(ProviderMetadataEntry(key="block.redacted_input", value=redacted_input))
    fallback_route = None
    if fallback_provider_kind is not None:
        fallback_route = "{0}->{1}:blocked".format(
            request.provider_kind,
            fallback_provider_kind,
        )
        metadata.extend(
            (
                ProviderMetadataEntry(key="fallback.candidate", value=fallback_provider_kind),
                ProviderMetadataEntry(key="fallback.selected", value=False),
            ),
        )
    return ProviderRuntimeResponse(
        decision="blocked",
        provider_kind=request.provider_kind,
        provider_id=request.provider_id,
        model_id=request.model_id,
        response_id="resp_wave10_blocked",
        content="",
        usage=ProviderUsage(input_tokens=0, output_tokens=0, budget_units=0, latency_ms=0),
        fallback_route=fallback_route,
        metadata=tuple(metadata),
    )


def blocked_boundary_result(
    request: ProviderBoundaryRequest,
    reason: str,
) -> ProviderBoundaryResult:
    return ProviderBoundaryResult(
        decision="blocked",
        requested_provider_kind=request.provider_kind,
        reason=reason,
    )


def boundary_result_from_response(
    *,
    request: ProviderBoundaryRequest,
    response: ProviderRuntimeResponse,
    adapter_invoked: bool,
    client_constructed: bool,
) -> ProviderBoundaryResult:
    return ProviderBoundaryResult(
        decision=response.decision,
        requested_provider_kind=request.provider_kind,
        reason=response.metadata_value("block.reason"),
        response=response,
        handler_executed=response.handler_executed,
        adapter_invoked=adapter_invoked,
        client_constructed=client_constructed,
        network_opened=response.network_opened,
        sdk_imported=response.sdk_imported,
        credential_material_accessed=response.credential_material_accessed,
        no_secret_echo=response.no_secret_echo,
    )
