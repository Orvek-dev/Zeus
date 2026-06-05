from __future__ import annotations

from typing import Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_provider_credentialed_http_runtime.http_client import provider_endpoint_is_loopback
from zeus_agent.live_provider_request_body_runtime import LiveProviderRequestBodyResult
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.security.credentials import redact_secret_spans


def safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def injection_reasons(injection: Optional[LiveCredentialInjectionResult]) -> tuple[str, ...]:
    if injection is None:
        return ("credential_injection_required",)
    reasons = []
    if injection.decision != "injection_ready" or not injection.credential_injection_ready:
        reasons.append("credential_injection_not_ready")
    if injection.adapter_kind != "provider":
        reasons.append("credential_injection_adapter_mismatch")
    if injection.header_name is None or injection.header_value_ref is None:
        reasons.append("credential_injection_header_missing")
    if injection.network_opened or injection.external_delivery_opened or injection.live_transport_enabled:
        reasons.append("credential_injection_side_effect_detected")
    if injection.raw_secret_returned or injection.material_released or not injection.no_secret_echo:
        reasons.append("credential_injection_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def provider_envelope_reasons(provider_envelope: Optional[LiveProviderRequestResult]) -> tuple[str, ...]:
    if provider_envelope is None:
        return ("provider_envelope_required",)
    reasons = []
    if provider_envelope.decision != "prepared" or not provider_envelope.request_prepared:
        reasons.append("provider_envelope_not_prepared")
    if provider_envelope.provider_kind != "openai_compatible":
        reasons.append("unsupported_provider_credentialed_http_kind")
    if provider_envelope.network_opened or provider_envelope.external_delivery_opened:
        reasons.append("provider_envelope_side_effect_detected")
    if provider_envelope.credential_material_accessed or provider_envelope.raw_secret_returned:
        reasons.append("provider_envelope_secret_boundary_failed")
    if provider_envelope.live_transport_enabled or provider_envelope.live_production_claimed or not provider_envelope.no_secret_echo:
        reasons.append("provider_envelope_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def request_body_reasons(request_body: Optional[LiveProviderRequestBodyResult]) -> tuple[str, ...]:
    if request_body is None:
        return ("provider_request_body_required",)
    reasons = []
    if request_body.decision != "materialized" or not request_body.provider_request_body_materialized:
        reasons.append("provider_request_body_not_materialized")
    if request_body.body_payload is None:
        reasons.append("provider_request_body_payload_required")
    if request_body.network_opened or request_body.external_delivery_opened:
        reasons.append("provider_request_body_side_effect_detected")
    if request_body.credential_material_accessed or request_body.raw_secret_returned or not request_body.no_secret_echo:
        reasons.append("provider_request_body_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def binding_reasons(
    injection: Optional[LiveCredentialInjectionResult],
    provider_envelope: Optional[LiveProviderRequestResult],
    request_body: Optional[LiveProviderRequestBodyResult],
) -> tuple[str, ...]:
    reasons = []
    if injection is not None and provider_envelope is not None and injection.material_proof_id != provider_envelope.material_proof_id:
        reasons.append("provider_credentialed_http_material_mismatch")
    if provider_envelope is not None and request_body is not None:
        if request_body.request_envelope_id != provider_envelope.request_envelope_id:
            reasons.append("provider_request_body_envelope_mismatch")
        if request_body.message_digest != provider_envelope.message_digest:
            reasons.append("provider_request_body_digest_mismatch")
    return tuple(dict.fromkeys(reasons))


def transport_reasons(endpoint: Optional[str], timeout_ms: int) -> tuple[str, ...]:
    reasons = []
    if endpoint is None:
        reasons.append("transport_endpoint_required")
    elif not provider_endpoint_is_loopback(endpoint):
        reasons.append("provider_credentialed_http_endpoint_not_loopback")
    if timeout_ms < 1 or timeout_ms > 30000:
        reasons.append("timeout_ms_out_of_bounds")
    return tuple(dict.fromkeys(reasons))
