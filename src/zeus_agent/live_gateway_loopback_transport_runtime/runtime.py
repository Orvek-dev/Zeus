from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.security.credentials import redact_secret_spans

LiveGatewayLoopbackDecision = Literal["executed", "blocked"]
GatewayTransportKind = Literal["loopback_delivery", "external_delivery"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_TRANSPORT_KINDS: Final = frozenset(("loopback_delivery", "external_delivery"))
_CLEANUP_RECEIPT: Final = "gateway-loopback-no-delivery"
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


class LiveGatewayLoopbackTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGatewayLoopbackDecision
    execution_id: Optional[str]
    activation_id: Optional[str]
    adapter_plan_id: Optional[str]
    delivery_envelope_id: Optional[str]
    transport_kind: Optional[GatewayTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    transport_activation_bound: bool = False
    adapter_plan_bound: bool = False
    gateway_envelope_bound: bool = False
    loopback_transport: bool = False
    delivery_attempted: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveGatewayLoopbackTransportRuntime:
    def execute(
        self,
        *,
        activation: Optional[LiveTransportActivationResult],
        adapter_plan: LiveGatewayAdapterResult,
        gateway_envelope: LiveGatewayDeliveryResult,
        transport_kind: str,
        execution_ref: str,
    ) -> LiveGatewayLoopbackTransportResult:
        safe_transport_kind = transport_kind.strip()
        safe_execution_ref = _safe_optional(execution_ref)
        reasons = list(_activation_reasons(activation=activation, adapter_plan=adapter_plan))
        reasons.extend(_adapter_plan_reasons(adapter_plan=adapter_plan, gateway_envelope=gateway_envelope))
        reasons.extend(_gateway_envelope_reasons(gateway_envelope))
        if safe_transport_kind not in _TRANSPORT_KINDS:
            reasons.append("unsupported_gateway_transport_kind")
        if safe_transport_kind == "external_delivery":
            reasons.append("gateway_external_delivery_not_implemented")
        if safe_execution_ref is None:
            reasons.append("execution_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                activation=activation,
                adapter_plan=adapter_plan,
                gateway_envelope=gateway_envelope,
                transport_kind=safe_transport_kind,
                execution_ref=safe_execution_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="executed",
            activation=activation,
            adapter_plan=adapter_plan,
            gateway_envelope=gateway_envelope,
            transport_kind=safe_transport_kind,
            execution_ref=safe_execution_ref,
            execution_id=_execution_id(
                activation=activation,
                adapter_plan=adapter_plan,
                gateway_envelope=gateway_envelope,
                transport_kind=safe_transport_kind,
                execution_ref=safe_execution_ref,
            ),
            transport_activation_bound=True,
            adapter_plan_bound=True,
            gateway_envelope_bound=True,
            loopback_transport=True,
            delivery_attempted=True,
            handler_executed=True,
            live_transport_enabled=True,
            execution_allowed=True,
            response=_loopback_response(gateway_envelope),
        )


def _activation_reasons(
    *,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveGatewayAdapterResult,
) -> tuple[str, ...]:
    if activation is None:
        return ("transport_activation_required",)
    reasons = []
    if activation.decision != "activation_ready" or not activation.transport_activation_ready:
        reasons.append("transport_activation_not_ready")
    if activation.adapter_kind != "gateway":
        reasons.append("transport_activation_not_gateway")
    if activation.adapter_plan_id != adapter_plan.adapter_plan_id:
        reasons.append("activation_adapter_plan_mismatch")
    if not activation.live_transport_authorized or activation.live_transport_enabled:
        reasons.append("transport_activation_policy_invalid")
    if activation.network_opened or activation.external_delivery_opened:
        reasons.append("transport_activation_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _adapter_plan_reasons(
    *,
    adapter_plan: LiveGatewayAdapterResult,
    gateway_envelope: LiveGatewayDeliveryResult,
) -> tuple[str, ...]:
    reasons = []
    if adapter_plan.decision != "planned" or not adapter_plan.adapter_plan_ready:
        reasons.append("adapter_plan_not_ready")
    if adapter_plan.delivery_envelope_id != gateway_envelope.delivery_envelope_id:
        reasons.append("adapter_gateway_envelope_mismatch")
    if adapter_plan.delivery_attempted or adapter_plan.external_delivery_opened:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.network_opened or adapter_plan.live_transport_enabled:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _gateway_envelope_reasons(gateway_envelope: LiveGatewayDeliveryResult) -> tuple[str, ...]:
    reasons = []
    if gateway_envelope.decision != "prepared" or not gateway_envelope.delivery_prepared:
        reasons.append("gateway_envelope_not_prepared")
    if gateway_envelope.delivery_attempted or gateway_envelope.external_delivery_opened:
        reasons.append("gateway_envelope_side_effect_detected")
    if gateway_envelope.credential_material_accessed or gateway_envelope.raw_secret_returned:
        reasons.append("gateway_envelope_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    *,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveGatewayAdapterResult,
    gateway_envelope: LiveGatewayDeliveryResult,
    transport_kind: str,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "activation_id": None if activation is None else activation.activation_id,
        "adapter_plan_id": adapter_plan.adapter_plan_id,
        "delivery_envelope_id": gateway_envelope.delivery_envelope_id,
        "execution_ref": execution_ref,
        "transport_kind": transport_kind,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-gateway-loopback-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _loopback_response(gateway_envelope: LiveGatewayDeliveryResult) -> dict[str, JsonValue]:
    return {
        "mode": "loopback_delivery",
        "adapter_id": gateway_envelope.adapter_id,
        "target": gateway_envelope.target,
        "message_digest": gateway_envelope.message_digest,
        "cleanup": _CLEANUP_RECEIPT,
    }


def _result(
    *,
    decision: LiveGatewayLoopbackDecision,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveGatewayAdapterResult,
    gateway_envelope: LiveGatewayDeliveryResult,
    transport_kind: str,
    execution_ref: Optional[str],
    execution_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    transport_activation_bound: bool = False,
    adapter_plan_bound: bool = False,
    gateway_envelope_bound: bool = False,
    loopback_transport: bool = False,
    delivery_attempted: bool = False,
    handler_executed: bool = False,
    live_transport_enabled: bool = False,
    execution_allowed: bool = False,
    response: Optional[dict[str, JsonValue]] = None,
) -> LiveGatewayLoopbackTransportResult:
    kind: Optional[GatewayTransportKind] = transport_kind if transport_kind in _TRANSPORT_KINDS else None
    result = LiveGatewayLoopbackTransportResult(
        decision=decision,
        execution_id=execution_id,
        activation_id=None if activation is None else activation.activation_id,
        adapter_plan_id=adapter_plan.adapter_plan_id,
        delivery_envelope_id=gateway_envelope.delivery_envelope_id,
        transport_kind=kind,
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        transport_activation_bound=transport_activation_bound,
        adapter_plan_bound=adapter_plan_bound,
        gateway_envelope_bound=gateway_envelope_bound,
        loopback_transport=loopback_transport,
        delivery_attempted=delivery_attempted,
        live_transport_enabled=live_transport_enabled,
        execution_allowed=execution_allowed,
        authority_granted=False,
        network_opened=False,
        handler_executed=handler_executed,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
        response=response,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveGatewayLoopbackTransportResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
