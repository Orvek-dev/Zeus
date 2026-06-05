from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_gateway_external_transport_runtime.response import no_secret_echo
from zeus_agent.security.credentials import redact_secret_spans

LiveGatewayDeliveryBodyDecision = Literal["materialized", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveGatewayDeliveryBodyResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGatewayDeliveryBodyDecision
    body_id: Optional[str]
    delivery_envelope_id: Optional[str]
    adapter_id: Optional[str]
    target: Optional[str]
    idempotency_key: Optional[str]
    message_digest: Optional[str]
    body_ref: Optional[str]
    body_payload: Optional[dict[str, JsonValue]]
    blocked_reasons: tuple[str, ...] = ()
    gateway_envelope_bound: bool = False
    message_digest_bound: bool = False
    gateway_delivery_body_materialized: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveGatewayDeliveryBodyRuntime:
    def materialize(
        self,
        *,
        gateway_envelope: Optional[LiveGatewayDeliveryResult],
        message: str,
        body_ref: str,
    ) -> LiveGatewayDeliveryBodyResult:
        safe_ref = _safe_optional(body_ref)
        safe_message = redact_secret_spans(message.strip())
        reasons = list(_envelope_reasons(gateway_envelope))
        if gateway_envelope is not None and gateway_envelope.message_digest != _message_digest(safe_message):
            reasons.append("message_digest_mismatch")
        if safe_message == "":
            reasons.append("message_required")
        if safe_ref is None:
            reasons.append("body_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                gateway_envelope=gateway_envelope,
                message_digest=_message_digest(safe_message) if safe_message else None,
                body_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="materialized",
            gateway_envelope=gateway_envelope,
            message_digest=_message_digest(safe_message),
            body_ref=safe_ref,
            body_payload=_body_payload(gateway_envelope, safe_message),
            body_id=_body_id(gateway_envelope, safe_ref, safe_message),
            gateway_envelope_bound=True,
            message_digest_bound=True,
            gateway_delivery_body_materialized=True,
        )


def _envelope_reasons(gateway_envelope: Optional[LiveGatewayDeliveryResult]) -> tuple[str, ...]:
    if gateway_envelope is None:
        return ("gateway_envelope_required",)
    reasons = []
    if gateway_envelope.decision != "prepared" or not gateway_envelope.delivery_prepared:
        reasons.append("gateway_envelope_not_prepared")
    if gateway_envelope.delivery_attempted or gateway_envelope.external_delivery_opened:
        reasons.append("gateway_envelope_side_effect_detected")
    if gateway_envelope.network_opened or gateway_envelope.handler_executed:
        reasons.append("gateway_envelope_side_effect_detected")
    if gateway_envelope.credential_material_accessed or gateway_envelope.raw_secret_returned:
        reasons.append("gateway_envelope_secret_boundary_failed")
    if gateway_envelope.live_transport_enabled or gateway_envelope.live_production_claimed:
        reasons.append("gateway_envelope_side_effect_detected")
    if not gateway_envelope.no_secret_echo:
        reasons.append("gateway_envelope_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def _body_payload(gateway_envelope: Optional[LiveGatewayDeliveryResult], message: str) -> dict[str, JsonValue]:
    return {
        "adapter_id": "" if gateway_envelope is None else gateway_envelope.adapter_id,
        "target": "" if gateway_envelope is None else gateway_envelope.target,
        "message": message,
        "idempotency_key": "" if gateway_envelope is None else gateway_envelope.idempotency_key,
    }


def _message_digest(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _body_id(
    gateway_envelope: Optional[LiveGatewayDeliveryResult],
    body_ref: Optional[str],
    message: str,
) -> str:
    payload = {
        "body_ref": body_ref,
        "delivery_envelope_id": None if gateway_envelope is None else gateway_envelope.delivery_envelope_id,
        "message_digest": _message_digest(message),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-gateway-delivery-body-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _result(
    *,
    decision: LiveGatewayDeliveryBodyDecision,
    gateway_envelope: Optional[LiveGatewayDeliveryResult],
    message_digest: Optional[str],
    body_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    body_payload: Optional[dict[str, JsonValue]] = None,
    body_id: Optional[str] = None,
    **flags: bool,
) -> LiveGatewayDeliveryBodyResult:
    result = LiveGatewayDeliveryBodyResult(
        decision=decision,
        body_id=body_id,
        delivery_envelope_id=None if gateway_envelope is None else gateway_envelope.delivery_envelope_id,
        adapter_id=None if gateway_envelope is None else gateway_envelope.adapter_id,
        target=None if gateway_envelope is None else gateway_envelope.target,
        idempotency_key=None if gateway_envelope is None else gateway_envelope.idempotency_key,
        message_digest=message_digest,
        body_ref=body_ref,
        body_payload=body_payload,
        blocked_reasons=blocked_reasons,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
