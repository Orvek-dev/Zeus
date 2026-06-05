from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional
from urllib.error import HTTPError, URLError

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_gateway_http_transport_runtime.http_client import (
    gateway_endpoint_is_loopback,
    post_gateway,
)
from zeus_agent.live_gateway_http_transport_runtime.secret_echo import no_secret_echo
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.security.credentials import redact_secret_spans

LiveGatewayHttpDecision = Literal["executed", "blocked"]
GatewayHttpTransportKind = Literal["local_http", "external_http"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_TRANSPORT_KINDS: Final = frozenset(("local_http", "external_http"))
_CLEANUP_RECEIPT: Final = "gateway-local-http-client-closed"


class LiveGatewayHttpTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGatewayHttpDecision
    execution_id: Optional[str]
    activation_id: Optional[str]
    adapter_plan_id: Optional[str]
    delivery_envelope_id: Optional[str]
    transport_kind: Optional[GatewayHttpTransportKind]
    delivery_endpoint: Optional[str]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    transport_activation_bound: bool = False
    adapter_plan_bound: bool = False
    gateway_envelope_bound: bool = False
    local_http_loopback: bool = False
    delivery_attempted: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
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


class LiveGatewayHttpTransportRuntime:
    def execute(
        self,
        *,
        activation: Optional[LiveTransportActivationResult],
        adapter_plan: LiveGatewayAdapterResult,
        gateway_envelope: LiveGatewayDeliveryResult,
        delivery_endpoint: str,
        transport_kind: str,
        execution_ref: str,
    ) -> LiveGatewayHttpTransportResult:
        safe_kind = transport_kind.strip()
        safe_endpoint = _safe_optional(delivery_endpoint)
        safe_ref = _safe_optional(execution_ref)
        reasons = list(_preflight_reasons(activation, adapter_plan, gateway_envelope, safe_kind, safe_endpoint, safe_ref))
        if reasons:
            return _result(
                decision="blocked",
                activation=activation,
                adapter_plan=adapter_plan,
                gateway_envelope=gateway_envelope,
                delivery_endpoint=safe_endpoint,
                transport_kind=safe_kind,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        try:
            client_result = post_gateway(gateway_envelope, safe_endpoint or "", adapter_plan.timeout_ms)
        except HTTPError as exc:
            return _blocked_after_network(
                activation, adapter_plan, gateway_envelope, safe_endpoint, safe_kind, safe_ref, "gateway_http_status_error", exc.code
            )
        except (TimeoutError, URLError):
            return _blocked_after_network(
                activation, adapter_plan, gateway_envelope, safe_endpoint, safe_kind, safe_ref, "gateway_http_transport_error", None
            )
        if client_result.redacted_payload is None:
            return _blocked_after_network(
                activation,
                adapter_plan,
                gateway_envelope,
                safe_endpoint,
                safe_kind,
                safe_ref,
                "gateway_http_response_not_json_object",
                client_result.status_code,
            )
        return _result(
            decision="executed",
            activation=activation,
            adapter_plan=adapter_plan,
            gateway_envelope=gateway_envelope,
            delivery_endpoint=safe_endpoint,
            transport_kind=safe_kind,
            execution_ref=safe_ref,
            execution_id=_execution_id(activation, adapter_plan, gateway_envelope, safe_endpoint, safe_kind, safe_ref),
            transport_activation_bound=True,
            adapter_plan_bound=True,
            gateway_envelope_bound=True,
            local_http_loopback=True,
            delivery_attempted=True,
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
    adapter_plan: LiveGatewayAdapterResult,
    gateway_envelope: LiveGatewayDeliveryResult,
    transport_kind: str,
    delivery_endpoint: Optional[str],
    execution_ref: Optional[str],
) -> tuple[str, ...]:
    reasons = []
    if activation is None:
        reasons.append("transport_activation_required")
    elif activation.decision != "activation_ready" or activation.adapter_kind != "gateway":
        reasons.append("transport_activation_not_gateway_ready")
    elif activation.adapter_plan_id != adapter_plan.adapter_plan_id:
        reasons.append("activation_adapter_plan_mismatch")
    if adapter_plan.decision != "planned" or not adapter_plan.adapter_plan_ready:
        reasons.append("adapter_plan_not_ready")
    if adapter_plan.delivery_envelope_id != gateway_envelope.delivery_envelope_id:
        reasons.append("adapter_gateway_envelope_mismatch")
    if gateway_envelope.decision != "prepared" or not gateway_envelope.delivery_prepared:
        reasons.append("gateway_envelope_not_prepared")
    if transport_kind not in _TRANSPORT_KINDS:
        reasons.append("unsupported_gateway_http_transport_kind")
    if transport_kind == "external_http":
        reasons.append("gateway_external_http_not_enabled")
    if delivery_endpoint is None or not gateway_endpoint_is_loopback(delivery_endpoint):
        reasons.append("gateway_http_endpoint_not_loopback")
    if execution_ref is None:
        reasons.append("execution_ref_required")
    return tuple(dict.fromkeys(reasons))


def _blocked_after_network(
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveGatewayAdapterResult,
    gateway_envelope: LiveGatewayDeliveryResult,
    delivery_endpoint: Optional[str],
    transport_kind: str,
    execution_ref: Optional[str],
    reason: str,
    status_code: Optional[int],
) -> LiveGatewayHttpTransportResult:
    return _result(
        decision="blocked",
        activation=activation,
        adapter_plan=adapter_plan,
        gateway_envelope=gateway_envelope,
        delivery_endpoint=delivery_endpoint,
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
    adapter_plan: LiveGatewayAdapterResult,
    gateway_envelope: LiveGatewayDeliveryResult,
    delivery_endpoint: Optional[str],
    transport_kind: str,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "activation_id": None if activation is None else activation.activation_id,
        "adapter_plan_id": adapter_plan.adapter_plan_id,
        "delivery_endpoint": delivery_endpoint,
        "delivery_envelope_id": gateway_envelope.delivery_envelope_id,
        "execution_ref": execution_ref,
        "transport_kind": transport_kind,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-gateway-http-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveGatewayHttpDecision,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveGatewayAdapterResult,
    gateway_envelope: LiveGatewayDeliveryResult,
    delivery_endpoint: Optional[str],
    transport_kind: str,
    execution_ref: Optional[str],
    execution_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    transport_activation_bound: bool = False,
    adapter_plan_bound: bool = False,
    gateway_envelope_bound: bool = False,
    local_http_loopback: bool = False,
    delivery_attempted: bool = False,
    live_transport_enabled: bool = False,
    execution_allowed: bool = False,
    network_opened: bool = False,
    handler_executed: bool = False,
    status_code: Optional[int] = None,
    latency_ms: Optional[int] = None,
    redacted_response: Optional[dict[str, JsonValue]] = None,
) -> LiveGatewayHttpTransportResult:
    kind: Optional[GatewayHttpTransportKind] = transport_kind if transport_kind in _TRANSPORT_KINDS else None
    result = LiveGatewayHttpTransportResult(
        decision=decision,
        execution_id=execution_id,
        activation_id=None if activation is None else activation.activation_id,
        adapter_plan_id=adapter_plan.adapter_plan_id,
        delivery_envelope_id=gateway_envelope.delivery_envelope_id,
        transport_kind=kind,
        delivery_endpoint=delivery_endpoint,
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if network_opened or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        transport_activation_bound=transport_activation_bound,
        adapter_plan_bound=adapter_plan_bound,
        gateway_envelope_bound=gateway_envelope_bound,
        local_http_loopback=local_http_loopback,
        delivery_attempted=delivery_attempted,
        live_transport_enabled=live_transport_enabled,
        execution_allowed=execution_allowed,
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
