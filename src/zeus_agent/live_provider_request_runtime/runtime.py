from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult
from zeus_agent.security.credentials import redact_secret_spans

LiveProviderRequestDecision = Literal["prepared", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ALLOWED_PROVIDER_KINDS: Final = frozenset(("openai_compatible", "anthropic_metadata"))
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


class LiveProviderRequestResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProviderRequestDecision
    request_envelope_id: Optional[str]
    provider_kind: str
    model_id: str
    endpoint: str
    endpoint_host: Optional[str]
    transport_lease_id: Optional[str]
    material_proof_id: Optional[str]
    message_digest: Optional[str] = None
    request_body_shape: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    request_prepared: bool = False
    secret_material_verified: bool = False
    provider_invoked: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProviderRequestRuntime:
    def prepare(
        self,
        *,
        transport_lease: Optional[LiveTransportLeaseResult],
        secret_material: Optional[LiveSecretMaterialResult],
        provider_kind: str,
        model_id: str,
        endpoint: str,
        message: str,
    ) -> LiveProviderRequestResult:
        safe_provider_kind = provider_kind.strip()
        safe_model_id = redact_secret_spans(model_id.strip())
        safe_endpoint = redact_secret_spans(endpoint.strip())
        safe_message = redact_secret_spans(message.strip())
        endpoint_host = _endpoint_host(safe_endpoint)
        reasons = list(_transport_reasons(transport_lease))
        reasons.extend(_secret_material_reasons(secret_material))
        if safe_provider_kind not in _ALLOWED_PROVIDER_KINDS:
            reasons.append("unsupported_provider_kind")
        if safe_model_id == "":
            reasons.append("model_required")
        if safe_message == "":
            reasons.append("message_required")
        if endpoint_host is None:
            reasons.append("malformed_provider_endpoint")
        if (
            endpoint_host is not None
            and transport_lease is not None
            and transport_lease.network_host != endpoint_host
        ):
            reasons.append("provider_endpoint_not_lease_bound")
        if reasons:
            return _result(
                decision="blocked",
                provider_kind=safe_provider_kind,
                model_id=safe_model_id,
                endpoint=safe_endpoint,
                endpoint_host=endpoint_host,
                transport_lease=transport_lease,
                secret_material=secret_material,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="prepared",
            provider_kind=safe_provider_kind,
            model_id=safe_model_id,
            endpoint=safe_endpoint,
            endpoint_host=endpoint_host,
            transport_lease=transport_lease,
            secret_material=secret_material,
            request_envelope_id=_request_envelope_id(
                transport_lease=transport_lease,
                secret_material=secret_material,
                provider_kind=safe_provider_kind,
                model_id=safe_model_id,
                endpoint=safe_endpoint,
                message=safe_message,
            ),
            message_digest=_message_digest(safe_message),
            request_body_shape={
                "model_id": safe_model_id,
                "message_count": 1,
                "stream": False,
            },
            request_prepared=True,
            secret_material_verified=True,
        )


def _transport_reasons(transport_lease: Optional[LiveTransportLeaseResult]) -> tuple[str, ...]:
    if transport_lease is None:
        return ("transport_lease_required",)
    reasons = []
    if transport_lease.decision != "bound" or not transport_lease.transport_lease_bound:
        reasons.append("transport_lease_not_bound")
    if transport_lease.runtime_kind != "provider":
        reasons.append("transport_lease_surface_not_provider")
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


def _endpoint_host(endpoint: str) -> Optional[str]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"https", "http"}:
        return None
    if parsed.hostname is None or parsed.hostname.strip() == "":
        return None
    return parsed.hostname


def _message_digest(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _request_envelope_id(
    *,
    transport_lease: Optional[LiveTransportLeaseResult],
    secret_material: Optional[LiveSecretMaterialResult],
    provider_kind: str,
    model_id: str,
    endpoint: str,
    message: str,
) -> str:
    payload = {
        "endpoint": endpoint,
        "material_proof_id": None if secret_material is None else secret_material.material_proof_id,
        "message_digest": _message_digest(message),
        "model_id": model_id,
        "provider_kind": provider_kind,
        "transport_lease_id": None if transport_lease is None else transport_lease.transport_lease_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-provider-request-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveProviderRequestDecision,
    provider_kind: str,
    model_id: str,
    endpoint: str,
    endpoint_host: Optional[str],
    transport_lease: Optional[LiveTransportLeaseResult],
    secret_material: Optional[LiveSecretMaterialResult],
    request_envelope_id: Optional[str] = None,
    message_digest: Optional[str] = None,
    request_body_shape: Optional[dict[str, JsonValue]] = None,
    blocked_reasons: tuple[str, ...] = (),
    request_prepared: bool = False,
    secret_material_verified: bool = False,
) -> LiveProviderRequestResult:
    result = LiveProviderRequestResult(
        decision=decision,
        request_envelope_id=request_envelope_id,
        provider_kind=provider_kind,
        model_id=model_id,
        endpoint=endpoint,
        endpoint_host=endpoint_host,
        transport_lease_id=None if transport_lease is None else transport_lease.transport_lease_id,
        material_proof_id=None if secret_material is None else secret_material.material_proof_id,
        message_digest=message_digest,
        request_body_shape=request_body_shape,
        blocked_reasons=blocked_reasons,
        request_prepared=request_prepared,
        secret_material_verified=secret_material_verified,
        provider_invoked=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveProviderRequestResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
