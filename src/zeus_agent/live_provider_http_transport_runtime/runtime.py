from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional
from urllib.error import HTTPError, URLError

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_provider_http_transport_runtime.http_client import (
    post_provider,
    provider_endpoint_is_loopback,
)
from zeus_agent.live_provider_http_transport_runtime.secret_echo import no_secret_echo
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.security.credentials import redact_secret_spans

LiveProviderHttpDecision = Literal["executed", "blocked"]
ProviderHttpTransportKind = Literal["local_http", "external_http"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_TRANSPORT_KINDS: Final = frozenset(("local_http", "external_http"))
_CLEANUP_RECEIPT: Final = "provider-local-http-client-closed"
class LiveProviderHttpTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProviderHttpDecision
    execution_id: Optional[str]
    activation_id: Optional[str]
    adapter_plan_id: Optional[str]
    request_envelope_id: Optional[str]
    transport_kind: Optional[ProviderHttpTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    transport_activation_bound: bool = False
    adapter_plan_bound: bool = False
    provider_envelope_bound: bool = False
    local_http_loopback: bool = False
    provider_invoked: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProviderHttpTransportRuntime:
    def execute(
        self,
        *,
        activation: Optional[LiveTransportActivationResult],
        adapter_plan: LiveProviderAdapterResult,
        provider_envelope: LiveProviderRequestResult,
        transport_kind: str,
        execution_ref: str,
    ) -> LiveProviderHttpTransportResult:
        safe_kind = transport_kind.strip()
        safe_ref = _safe_optional(execution_ref)
        reasons = list(_preflight_reasons(activation, adapter_plan, provider_envelope, safe_kind, safe_ref))
        if reasons:
            return _result(
                decision="blocked",
                activation=activation,
                adapter_plan=adapter_plan,
                provider_envelope=provider_envelope,
                transport_kind=safe_kind,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        try:
            client_result = post_provider(provider_envelope, adapter_plan.timeout_ms)
        except HTTPError as exc:
            return _blocked_after_network(
                activation, adapter_plan, provider_envelope, safe_kind, safe_ref, "provider_http_status_error", exc.code
            )
        except (TimeoutError, URLError):
            return _blocked_after_network(
                activation, adapter_plan, provider_envelope, safe_kind, safe_ref, "provider_http_transport_error", None
            )
        if client_result.redacted_payload is None:
            return _blocked_after_network(
                activation,
                adapter_plan,
                provider_envelope,
                safe_kind,
                safe_ref,
                "provider_http_response_not_json_object",
                client_result.status_code,
            )
        return _result(
            decision="executed",
            activation=activation,
            adapter_plan=adapter_plan,
            provider_envelope=provider_envelope,
            transport_kind=safe_kind,
            execution_ref=safe_ref,
            execution_id=_execution_id(activation, adapter_plan, provider_envelope, safe_kind, safe_ref),
            transport_activation_bound=True,
            adapter_plan_bound=True,
            provider_envelope_bound=True,
            local_http_loopback=True,
            provider_invoked=True,
            live_transport_enabled=True,
            execution_allowed=True,
            network_opened=True,
            handler_executed=True,
            status_code=client_result.status_code,
            latency_ms=client_result.latency_ms,
            redacted_response=client_result.redacted_payload,
        )


def _preflight_reasons(
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveProviderAdapterResult,
    provider_envelope: LiveProviderRequestResult,
    transport_kind: str,
    execution_ref: Optional[str],
) -> tuple[str, ...]:
    reasons = []
    if activation is None:
        reasons.append("transport_activation_required")
    elif activation.decision != "activation_ready" or activation.adapter_kind != "provider":
        reasons.append("transport_activation_not_provider_ready")
    elif activation.adapter_plan_id != adapter_plan.adapter_plan_id:
        reasons.append("activation_adapter_plan_mismatch")
    if adapter_plan.decision != "planned" or not adapter_plan.adapter_plan_ready:
        reasons.append("adapter_plan_not_ready")
    if adapter_plan.request_envelope_id != provider_envelope.request_envelope_id:
        reasons.append("adapter_provider_envelope_mismatch")
    if provider_envelope.decision != "prepared" or not provider_envelope.request_prepared:
        reasons.append("provider_envelope_not_prepared")
    if transport_kind not in _TRANSPORT_KINDS:
        reasons.append("unsupported_provider_http_transport_kind")
    if transport_kind == "external_http":
        reasons.append("provider_external_http_not_enabled")
    if not provider_endpoint_is_loopback(provider_envelope.endpoint):
        reasons.append("provider_http_endpoint_not_loopback")
    if execution_ref is None:
        reasons.append("execution_ref_required")
    return tuple(dict.fromkeys(reasons))


def _blocked_after_network(
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveProviderAdapterResult,
    provider_envelope: LiveProviderRequestResult,
    transport_kind: str,
    execution_ref: Optional[str],
    reason: str,
    status_code: Optional[int],
) -> LiveProviderHttpTransportResult:
    return _result(
        decision="blocked",
        activation=activation,
        adapter_plan=adapter_plan,
        provider_envelope=provider_envelope,
        transport_kind=transport_kind,
        execution_ref=execution_ref,
        blocked_reasons=(reason,),
        network_opened=True,
        status_code=status_code,
    )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveProviderAdapterResult,
    provider_envelope: LiveProviderRequestResult,
    transport_kind: str,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "activation_id": None if activation is None else activation.activation_id,
        "adapter_plan_id": adapter_plan.adapter_plan_id,
        "execution_ref": execution_ref,
        "request_envelope_id": provider_envelope.request_envelope_id,
        "transport_kind": transport_kind,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-provider-http-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveProviderHttpDecision,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveProviderAdapterResult,
    provider_envelope: LiveProviderRequestResult,
    transport_kind: str,
    execution_ref: Optional[str],
    execution_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    transport_activation_bound: bool = False,
    adapter_plan_bound: bool = False,
    provider_envelope_bound: bool = False,
    local_http_loopback: bool = False,
    provider_invoked: bool = False,
    live_transport_enabled: bool = False,
    execution_allowed: bool = False,
    network_opened: bool = False,
    handler_executed: bool = False,
    status_code: Optional[int] = None,
    latency_ms: Optional[int] = None,
    redacted_response: Optional[dict[str, JsonValue]] = None,
) -> LiveProviderHttpTransportResult:
    kind: Optional[ProviderHttpTransportKind] = transport_kind if transport_kind in _TRANSPORT_KINDS else None
    result = LiveProviderHttpTransportResult(
        decision=decision,
        execution_id=execution_id,
        activation_id=None if activation is None else activation.activation_id,
        adapter_plan_id=adapter_plan.adapter_plan_id,
        request_envelope_id=provider_envelope.request_envelope_id,
        transport_kind=kind,
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if network_opened or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        transport_activation_bound=transport_activation_bound,
        adapter_plan_bound=adapter_plan_bound,
        provider_envelope_bound=provider_envelope_bound,
        local_http_loopback=local_http_loopback,
        provider_invoked=provider_invoked,
        live_transport_enabled=live_transport_enabled,
        execution_allowed=execution_allowed,
        authority_granted=False,
        network_opened=network_opened,
        non_loopback_network_opened=False,
        handler_executed=handler_executed,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
        status_code=status_code,
        latency_ms=latency_ms,
        redacted_response=redacted_response,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
