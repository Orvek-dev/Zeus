from __future__ import annotations

from typing import Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_gateway_credentialed_http_runtime.http_client import gateway_endpoint_is_loopback
from zeus_agent.live_gateway_delivery_body_runtime import LiveGatewayDeliveryBodyResult
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
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
    if injection.adapter_kind != "gateway":
        reasons.append("credential_injection_adapter_mismatch")
    if injection.header_name is None or injection.header_value_ref is None:
        reasons.append("credential_injection_header_missing")
    if injection.network_opened or injection.external_delivery_opened or injection.live_transport_enabled:
        reasons.append("credential_injection_side_effect_detected")
    if injection.raw_secret_returned or injection.material_released or not injection.no_secret_echo:
        reasons.append("credential_injection_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def gateway_envelope_reasons(gateway_envelope: Optional[LiveGatewayDeliveryResult]) -> tuple[str, ...]:
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
    if gateway_envelope.live_transport_enabled or gateway_envelope.live_production_claimed or not gateway_envelope.no_secret_echo:
        reasons.append("gateway_envelope_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def delivery_body_reasons(delivery_body: Optional[LiveGatewayDeliveryBodyResult]) -> tuple[str, ...]:
    if delivery_body is None:
        return ("gateway_delivery_body_required",)
    reasons = []
    if delivery_body.decision != "materialized" or not delivery_body.gateway_delivery_body_materialized:
        reasons.append("gateway_delivery_body_not_materialized")
    if delivery_body.body_payload is None:
        reasons.append("gateway_delivery_body_payload_required")
    if delivery_body.network_opened or delivery_body.external_delivery_opened:
        reasons.append("gateway_delivery_body_side_effect_detected")
    if delivery_body.credential_material_accessed or delivery_body.raw_secret_returned or not delivery_body.no_secret_echo:
        reasons.append("gateway_delivery_body_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def binding_reasons(
    injection: Optional[LiveCredentialInjectionResult],
    gateway_envelope: Optional[LiveGatewayDeliveryResult],
    delivery_body: Optional[LiveGatewayDeliveryBodyResult],
) -> tuple[str, ...]:
    reasons = []
    if injection is not None and gateway_envelope is not None and injection.material_proof_id != gateway_envelope.material_proof_id:
        reasons.append("gateway_credentialed_http_material_mismatch")
    if gateway_envelope is not None and delivery_body is not None:
        if delivery_body.delivery_envelope_id != gateway_envelope.delivery_envelope_id:
            reasons.append("gateway_delivery_body_envelope_mismatch")
        if delivery_body.message_digest != gateway_envelope.message_digest:
            reasons.append("gateway_delivery_body_digest_mismatch")
    return tuple(dict.fromkeys(reasons))


def transport_reasons(endpoint: Optional[str], timeout_ms: int) -> tuple[str, ...]:
    reasons = []
    if endpoint is None:
        reasons.append("delivery_endpoint_required")
    elif not gateway_endpoint_is_loopback(endpoint):
        reasons.append("gateway_credentialed_http_endpoint_not_loopback")
    if timeout_ms < 1 or timeout_ms > 30000:
        reasons.append("timeout_ms_out_of_bounds")
    return tuple(dict.fromkeys(reasons))
