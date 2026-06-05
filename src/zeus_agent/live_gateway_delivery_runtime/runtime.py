from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.gateway_runtime import default_gateway_adapter_specs
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult
from zeus_agent.security.credentials import redact_secret_spans

LiveGatewayDeliveryDecision = Literal["prepared", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_KNOWN_ADAPTERS: Final = frozenset(adapter.adapter_id for adapter in default_gateway_adapter_specs())
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


class LiveGatewayDeliveryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveGatewayDeliveryDecision
    delivery_envelope_id: Optional[str]
    adapter_id: str
    target: str
    idempotency_key: str
    transport_lease_id: Optional[str]
    material_proof_id: Optional[str]
    message_digest: Optional[str] = None
    blocked_reasons: tuple[str, ...] = ()
    delivery_prepared: bool = False
    delivery_target_allowlisted: bool = False
    secret_material_verified: bool = False
    delivery_attempted: bool = False
    external_delivery_opened: bool = False
    provider_invoked: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveGatewayDeliveryRuntime:
    def prepare(
        self,
        *,
        transport_lease: Optional[LiveTransportLeaseResult],
        secret_material: Optional[LiveSecretMaterialResult],
        adapter_id: str,
        target: str,
        message: str,
        idempotency_key: str,
    ) -> LiveGatewayDeliveryResult:
        safe_adapter_id = redact_secret_spans(adapter_id.strip())
        safe_target = redact_secret_spans(target.strip())
        safe_message = redact_secret_spans(message.strip())
        safe_idempotency_key = redact_secret_spans(idempotency_key.strip())
        target_allowlisted = _target_allowlisted(adapter_id=safe_adapter_id, target=safe_target)
        reasons = list(_transport_reasons(transport_lease))
        reasons.extend(_secret_material_reasons(secret_material))
        if safe_adapter_id not in _KNOWN_ADAPTERS:
            reasons.append("unknown_gateway_adapter")
        if not target_allowlisted:
            reasons.append("delivery_target_not_allowlisted")
        if safe_message == "":
            reasons.append("message_required")
        if safe_idempotency_key == "":
            reasons.append("idempotency_key_required")
        if reasons:
            return _result(
                decision="blocked",
                adapter_id=safe_adapter_id,
                target=safe_target,
                idempotency_key=safe_idempotency_key,
                transport_lease=transport_lease,
                secret_material=secret_material,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                delivery_target_allowlisted=target_allowlisted,
            )
        return _result(
            decision="prepared",
            adapter_id=safe_adapter_id,
            target=safe_target,
            idempotency_key=safe_idempotency_key,
            transport_lease=transport_lease,
            secret_material=secret_material,
            delivery_envelope_id=_delivery_envelope_id(
                transport_lease=transport_lease,
                secret_material=secret_material,
                adapter_id=safe_adapter_id,
                target=safe_target,
                message=safe_message,
                idempotency_key=safe_idempotency_key,
            ),
            message_digest=_message_digest(safe_message),
            delivery_prepared=True,
            delivery_target_allowlisted=True,
            secret_material_verified=True,
        )


def _transport_reasons(transport_lease: Optional[LiveTransportLeaseResult]) -> tuple[str, ...]:
    if transport_lease is None:
        return ("transport_lease_required",)
    reasons = []
    if transport_lease.decision != "bound" or not transport_lease.transport_lease_bound:
        reasons.append("transport_lease_not_bound")
    if transport_lease.runtime_kind != "gateway":
        reasons.append("transport_lease_surface_not_gateway")
    if transport_lease.live_transport_enabled or transport_lease.network_opened:
        reasons.append("transport_lease_side_effect_detected")
    if transport_lease.handler_executed or transport_lease.external_delivery_opened:
        reasons.append("transport_lease_side_effect_detected")
    if transport_lease.credential_material_accessed or transport_lease.live_production_claimed:
        reasons.append("transport_lease_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _secret_material_reasons(secret_material: Optional[LiveSecretMaterialResult]) -> tuple[str, ...]:
    if secret_material is None:
        return ("secret_material_proof_required",)
    reasons = []
    if secret_material.decision != "available" or not secret_material.material_available:
        reasons.append("secret_material_not_available")
    if secret_material.raw_secret_returned or secret_material.material_released:
        reasons.append("secret_material_leak_detected")
    if secret_material.network_opened or secret_material.external_delivery_opened:
        reasons.append("secret_material_side_effect_detected")
    if secret_material.live_production_claimed:
        reasons.append("secret_material_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _target_allowlisted(*, adapter_id: str, target: str) -> bool:
    return target.startswith("{0}://".format(adapter_id))


def _message_digest(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _delivery_envelope_id(
    *,
    transport_lease: Optional[LiveTransportLeaseResult],
    secret_material: Optional[LiveSecretMaterialResult],
    adapter_id: str,
    target: str,
    message: str,
    idempotency_key: str,
) -> str:
    payload = {
        "adapter_id": adapter_id,
        "idempotency_key": idempotency_key,
        "material_proof_id": None if secret_material is None else secret_material.material_proof_id,
        "message_digest": _message_digest(message),
        "target": target,
        "transport_lease_id": None if transport_lease is None else transport_lease.transport_lease_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-gateway-delivery-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveGatewayDeliveryDecision,
    adapter_id: str,
    target: str,
    idempotency_key: str,
    transport_lease: Optional[LiveTransportLeaseResult],
    secret_material: Optional[LiveSecretMaterialResult],
    delivery_envelope_id: Optional[str] = None,
    message_digest: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    delivery_prepared: bool = False,
    delivery_target_allowlisted: bool = False,
    secret_material_verified: bool = False,
) -> LiveGatewayDeliveryResult:
    result = LiveGatewayDeliveryResult(
        decision=decision,
        delivery_envelope_id=delivery_envelope_id,
        adapter_id=adapter_id,
        target=target,
        idempotency_key=idempotency_key,
        transport_lease_id=None if transport_lease is None else transport_lease.transport_lease_id,
        material_proof_id=None if secret_material is None else secret_material.material_proof_id,
        message_digest=message_digest,
        blocked_reasons=blocked_reasons,
        delivery_prepared=delivery_prepared,
        delivery_target_allowlisted=delivery_target_allowlisted,
        secret_material_verified=secret_material_verified,
        delivery_attempted=False,
        external_delivery_opened=False,
        provider_invoked=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        network_opened=False,
        handler_executed=False,
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveGatewayDeliveryResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
