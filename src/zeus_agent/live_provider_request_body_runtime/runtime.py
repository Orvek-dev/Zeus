from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_mcp_external_transport_runtime.response import no_secret_echo
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.security.credentials import redact_secret_spans

LiveProviderRequestBodyDecision = Literal["materialized", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveProviderRequestBodyResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProviderRequestBodyDecision
    body_id: Optional[str]
    request_envelope_id: Optional[str]
    provider_kind: Optional[str]
    model_id: Optional[str]
    message_digest: Optional[str]
    body_ref: Optional[str]
    body_payload: Optional[dict[str, JsonValue]]
    blocked_reasons: tuple[str, ...] = ()
    provider_envelope_bound: bool = False
    message_digest_bound: bool = False
    provider_request_body_materialized: bool = False
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


class LiveProviderRequestBodyRuntime:
    def materialize(
        self,
        *,
        provider_envelope: Optional[LiveProviderRequestResult],
        message: str,
        body_ref: str,
    ) -> LiveProviderRequestBodyResult:
        safe_ref = _safe_optional(body_ref)
        safe_message = redact_secret_spans(message.strip())
        reasons = list(_envelope_reasons(provider_envelope))
        if provider_envelope is not None and provider_envelope.message_digest != _message_digest(safe_message):
            reasons.append("message_digest_mismatch")
        if safe_message == "":
            reasons.append("message_required")
        if safe_ref is None:
            reasons.append("body_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                provider_envelope=provider_envelope,
                message_digest=_message_digest(safe_message) if safe_message else None,
                body_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        body_payload = _body_payload(provider_envelope, safe_message)
        return _result(
            decision="materialized",
            provider_envelope=provider_envelope,
            message_digest=_message_digest(safe_message),
            body_ref=safe_ref,
            body_payload=body_payload,
            body_id=_body_id(provider_envelope, safe_ref, safe_message),
            provider_envelope_bound=True,
            message_digest_bound=True,
            provider_request_body_materialized=True,
        )


def _envelope_reasons(provider_envelope: Optional[LiveProviderRequestResult]) -> tuple[str, ...]:
    if provider_envelope is None:
        return ("provider_envelope_required",)
    reasons = []
    if provider_envelope.decision != "prepared" or not provider_envelope.request_prepared:
        reasons.append("provider_envelope_not_prepared")
    if provider_envelope.provider_kind != "openai_compatible":
        reasons.append("unsupported_provider_body_kind")
    if provider_envelope.network_opened or provider_envelope.external_delivery_opened:
        reasons.append("provider_envelope_side_effect_detected")
    if provider_envelope.credential_material_accessed or provider_envelope.raw_secret_returned:
        reasons.append("provider_envelope_secret_boundary_failed")
    if provider_envelope.live_transport_enabled or provider_envelope.live_production_claimed:
        reasons.append("provider_envelope_side_effect_detected")
    if not provider_envelope.no_secret_echo:
        reasons.append("provider_envelope_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def _body_payload(provider_envelope: Optional[LiveProviderRequestResult], message: str) -> dict[str, JsonValue]:
    return {
        "model": "" if provider_envelope is None else provider_envelope.model_id,
        "messages": [
            {
                "role": "user",
                "content": message,
            }
        ],
        "stream": False,
    }


def _message_digest(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _body_id(
    provider_envelope: Optional[LiveProviderRequestResult],
    body_ref: Optional[str],
    message: str,
) -> str:
    payload = {
        "body_ref": body_ref,
        "message_digest": _message_digest(message),
        "request_envelope_id": None if provider_envelope is None else provider_envelope.request_envelope_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-provider-request-body-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _result(
    *,
    decision: LiveProviderRequestBodyDecision,
    provider_envelope: Optional[LiveProviderRequestResult],
    message_digest: Optional[str],
    body_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    body_payload: Optional[dict[str, JsonValue]] = None,
    body_id: Optional[str] = None,
    **flags: bool,
) -> LiveProviderRequestBodyResult:
    result = LiveProviderRequestBodyResult(
        decision=decision,
        body_id=body_id,
        request_envelope_id=None if provider_envelope is None else provider_envelope.request_envelope_id,
        provider_kind=None if provider_envelope is None else provider_envelope.provider_kind,
        model_id=None if provider_envelope is None else provider_envelope.model_id,
        message_digest=message_digest,
        body_ref=body_ref,
        body_payload=body_payload,
        blocked_reasons=blocked_reasons,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
