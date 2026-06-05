from __future__ import annotations

from typing import Optional

from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult


def envelope_id_and_reasons(
    *,
    envelope_kind: str,
    envelope: dict[str, JsonValue],
) -> tuple[Optional[str], tuple[str, ...]]:
    if envelope_kind == "provider":
        return _provider_envelope_id(envelope)
    if envelope_kind == "gateway":
        return _gateway_envelope_id(envelope)
    if envelope_kind == "mcp":
        return _mcp_envelope_id(envelope)
    return None, ()


def _provider_envelope_id(envelope: dict[str, JsonValue]) -> tuple[Optional[str], tuple[str, ...]]:
    try:
        parsed = LiveProviderRequestResult.model_validate(envelope)
    except ValidationError:
        return None, ("malformed_provider_envelope",)
    reasons = []
    if parsed.decision != "prepared" or not parsed.request_prepared:
        reasons.append("provider_envelope_not_prepared")
    if parsed.provider_invoked or parsed.network_opened or parsed.handler_executed:
        reasons.append("provider_envelope_side_effect_detected")
    if parsed.credential_material_accessed or parsed.raw_secret_returned:
        reasons.append("provider_envelope_secret_leak_detected")
    return parsed.request_envelope_id, tuple(dict.fromkeys(reasons))


def _gateway_envelope_id(envelope: dict[str, JsonValue]) -> tuple[Optional[str], tuple[str, ...]]:
    try:
        parsed = LiveGatewayDeliveryResult.model_validate(envelope)
    except ValidationError:
        return None, ("malformed_gateway_envelope",)
    reasons = []
    if parsed.decision != "prepared" or not parsed.delivery_prepared:
        reasons.append("gateway_envelope_not_prepared")
    if parsed.delivery_attempted or parsed.network_opened or parsed.handler_executed:
        reasons.append("gateway_envelope_side_effect_detected")
    if parsed.credential_material_accessed or parsed.raw_secret_returned:
        reasons.append("gateway_envelope_secret_leak_detected")
    return parsed.delivery_envelope_id, tuple(dict.fromkeys(reasons))


def _mcp_envelope_id(envelope: dict[str, JsonValue]) -> tuple[Optional[str], tuple[str, ...]]:
    try:
        parsed = LiveMcpRequestResult.model_validate(envelope)
    except ValidationError:
        return None, ("malformed_mcp_envelope",)
    reasons = []
    if parsed.decision != "prepared" or not parsed.request_prepared:
        reasons.append("mcp_envelope_not_prepared")
    if parsed.tool_invoked or parsed.server_started or parsed.network_opened:
        reasons.append("mcp_envelope_side_effect_detected")
    if parsed.credential_material_accessed or parsed.raw_secret_returned:
        reasons.append("mcp_envelope_secret_leak_detected")
    return parsed.request_envelope_id, tuple(dict.fromkeys(reasons))
