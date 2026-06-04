from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import ValidationError

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderUsage,
)
from zeus_agent.runtime_lease import RuntimeLeaseIntakeResult

_LOOPBACK_HOSTS: Final = {"127.0.0.1", "localhost"}


@dataclass(frozen=True)
class LiveHttpConfig:
    endpoint: str
    endpoint_host: str
    approval_receipt: ApprovalReceipt
    timeout_ms: int


@dataclass(frozen=True)
class LiveHttpResult:
    body: str
    status_code: int
    latency_ms: int


def live_http_config(
    request: ProviderRuntimeRequest,
    authorization: RuntimeLeaseIntakeResult,
) -> LiveHttpConfig | ProviderRuntimeResponse | None:
    endpoint = _metadata_text(request, "live.endpoint")
    if endpoint is None:
        return None
    if not request.live_network:
        return http_blocked_response(request, "live_network_required")
    approval = _approval_receipt(request, authorization)
    if isinstance(approval, ProviderRuntimeResponse):
        return approval
    timeout_ms = _metadata_positive_int(request, "live.timeout_ms")
    if timeout_ms is None:
        return http_blocked_response(request, "missing_timeout")
    parsed = urlparse(endpoint)
    endpoint_host = parsed.hostname or ""
    if parsed.scheme != "http" or endpoint_host == "":
        return http_blocked_response(request, "non_loopback_endpoint")
    if request.network_host is None or endpoint_host != request.network_host:
        return http_blocked_response(
            request,
            "network_host_mismatch",
            endpoint_host=endpoint_host,
        )
    if endpoint_host not in _LOOPBACK_HOSTS:
        return http_blocked_response(
            request,
            "non_loopback_endpoint",
            endpoint_host=endpoint_host,
        )
    return LiveHttpConfig(
        endpoint=endpoint,
        endpoint_host=endpoint_host,
        approval_receipt=approval,
        timeout_ms=timeout_ms,
    )


def post_json(config: LiveHttpConfig, payload: dict[str, object]) -> LiveHttpResult:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        config.endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with urlopen(request, timeout=config.timeout_ms / 1000) as response:
        response_body = response.read().decode("utf-8")
        status_code = int(response.status)
    latency_ms = int((time.monotonic() - started) * 1000)
    return LiveHttpResult(body=response_body, status_code=status_code, latency_ms=latency_ms)


def parse_json_object(result: LiveHttpResult) -> dict[str, object] | None:
    try:
        payload = json.loads(result.body)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def http_error_response(
    request: ProviderRuntimeRequest,
    reason: str,
    *,
    config: LiveHttpConfig | None = None,
    network_opened: bool = False,
    status_code: int | None = None,
) -> ProviderRuntimeResponse:
    return http_blocked_response(
        request,
        reason,
        endpoint_host=None if config is None else config.endpoint_host,
        network_opened=network_opened,
        status_code=status_code,
    )


def http_blocked_response(
    request: ProviderRuntimeRequest,
    reason: str,
    *,
    endpoint_host: str | None = None,
    network_opened: bool = False,
    status_code: int | None = None,
) -> ProviderRuntimeResponse:
    metadata = [
        ProviderMetadataEntry(key="block.reason", value=reason),
        ProviderMetadataEntry(key="audit.record_created", value=True),
    ]
    if endpoint_host is not None:
        metadata.append(ProviderMetadataEntry(key="http.endpoint_host", value=endpoint_host))
    if status_code is not None:
        metadata.append(ProviderMetadataEntry(key="http.status_code", value=status_code))
    return ProviderRuntimeResponse(
        decision="blocked",
        provider_kind=request.provider_kind,
        provider_id=request.provider_id,
        model_id=request.model_id,
        response_id="resp_wave16_http_blocked",
        content="",
        usage=ProviderUsage(input_tokens=0, output_tokens=0, budget_units=0, latency_ms=0),
        metadata=tuple(metadata),
        handler_executed=False,
        network_opened=network_opened,
    )


def live_http_metadata(
    config: LiveHttpConfig,
    authorization: RuntimeLeaseIntakeResult,
    result: LiveHttpResult,
) -> tuple[ProviderMetadataEntry, ...]:
    return (
        ProviderMetadataEntry(key="http.endpoint_host", value=config.endpoint_host),
        ProviderMetadataEntry(key="http.status_code", value=result.status_code),
        ProviderMetadataEntry(key="approval.receipt_checked", value=True),
        ProviderMetadataEntry(key="timeout.enforced", value=True),
        ProviderMetadataEntry(key="audit.record_created", value=True),
        ProviderMetadataEntry(key="lease.evidence_target", value=authorization.evidence_target or ""),
    )


def _metadata_text(request: ProviderRuntimeRequest, key: str) -> str | None:
    value = request.metadata_value(key)
    if isinstance(value, str) and value.strip() != "":
        return value.strip()
    return None


def _metadata_positive_int(request: ProviderRuntimeRequest, key: str) -> int | None:
    value = request.metadata_value(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def _approval_receipt(
    request: ProviderRuntimeRequest,
    authorization: RuntimeLeaseIntakeResult,
) -> ApprovalReceipt | ProviderRuntimeResponse:
    approval = _metadata_text(request, "approval.receipt")
    if approval is None:
        return http_blocked_response(request, "missing_approval")
    try:
        receipt = ApprovalReceipt.model_validate_json(approval)
    except ValidationError:
        return http_blocked_response(request, "invalid_approval")
    authority = authorization.authority
    if authority is None:
        return http_blocked_response(request, "approval_outside_authority")
    if authorization.capability_id not in set(receipt.approved_capabilities):
        return http_blocked_response(request, "approval_missing_capability")
    try:
        receipt.assert_within_authority(authority)
    except ValueError:
        return http_blocked_response(request, "approval_outside_authority")
    return receipt


def transport_failure_reason(exc: HTTPError | URLError | TimeoutError) -> str:
    if isinstance(exc, HTTPError):
        return "http_status_error"
    if isinstance(exc, TimeoutError):
        return "http_timeout"
    return "http_transport_error"
