from __future__ import annotations

from typing import Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_mcp_credentialed_http_runtime.http_client import mcp_endpoint_is_loopback
from zeus_agent.live_mcp_request_body_runtime import LiveMcpRequestBodyResult
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
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
    if injection.adapter_kind != "mcp":
        reasons.append("credential_injection_adapter_mismatch")
    if injection.header_name is None or injection.header_value_ref is None:
        reasons.append("credential_injection_header_missing")
    if injection.network_opened or injection.external_delivery_opened or injection.live_transport_enabled:
        reasons.append("credential_injection_side_effect_detected")
    if injection.raw_secret_returned or injection.material_released or not injection.no_secret_echo:
        reasons.append("credential_injection_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def mcp_envelope_reasons(mcp_envelope: Optional[LiveMcpRequestResult]) -> tuple[str, ...]:
    if mcp_envelope is None:
        return ("mcp_envelope_required",)
    reasons = []
    if mcp_envelope.decision != "prepared" or not mcp_envelope.request_prepared:
        reasons.append("mcp_envelope_not_prepared")
    if mcp_envelope.server_started or mcp_envelope.resources_enabled or mcp_envelope.prompts_enabled:
        reasons.append("mcp_envelope_side_effect_detected")
    if mcp_envelope.tool_invoked or mcp_envelope.network_opened or mcp_envelope.handler_executed:
        reasons.append("mcp_envelope_side_effect_detected")
    if mcp_envelope.credential_material_accessed or mcp_envelope.raw_secret_returned:
        reasons.append("mcp_envelope_secret_boundary_failed")
    if mcp_envelope.live_transport_enabled or mcp_envelope.live_production_claimed or not mcp_envelope.no_secret_echo:
        reasons.append("mcp_envelope_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def request_body_reasons(request_body: Optional[LiveMcpRequestBodyResult]) -> tuple[str, ...]:
    if request_body is None:
        return ("mcp_request_body_required",)
    reasons = []
    if request_body.decision != "materialized" or not request_body.mcp_request_body_materialized:
        reasons.append("mcp_request_body_not_materialized")
    if request_body.body_payload is None:
        reasons.append("mcp_request_body_payload_required")
    if request_body.server_started or request_body.resources_enabled or request_body.prompts_enabled:
        reasons.append("mcp_request_body_side_effect_detected")
    if request_body.tool_invoked or request_body.network_opened or request_body.external_delivery_opened:
        reasons.append("mcp_request_body_side_effect_detected")
    if request_body.credential_material_accessed or request_body.raw_secret_returned or not request_body.no_secret_echo:
        reasons.append("mcp_request_body_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def binding_reasons(
    injection: Optional[LiveCredentialInjectionResult],
    mcp_envelope: Optional[LiveMcpRequestResult],
    request_body: Optional[LiveMcpRequestBodyResult],
) -> tuple[str, ...]:
    reasons = []
    if injection is not None and mcp_envelope is not None and injection.material_proof_id != mcp_envelope.material_proof_id:
        reasons.append("mcp_credentialed_http_material_mismatch")
    if mcp_envelope is not None and request_body is not None:
        if request_body.request_envelope_id != mcp_envelope.request_envelope_id:
            reasons.append("mcp_request_body_envelope_mismatch")
        if request_body.arguments_digest != mcp_envelope.arguments_digest:
            reasons.append("mcp_request_body_arguments_mismatch")
    return tuple(dict.fromkeys(reasons))


def transport_reasons(endpoint: Optional[str], timeout_ms: int) -> tuple[str, ...]:
    reasons = []
    if endpoint is None:
        reasons.append("transport_endpoint_required")
    elif not mcp_endpoint_is_loopback(endpoint):
        reasons.append("mcp_credentialed_http_endpoint_not_loopback")
    if timeout_ms < 1 or timeout_ms > 30000:
        reasons.append("timeout_ms_out_of_bounds")
    return tuple(dict.fromkeys(reasons))
