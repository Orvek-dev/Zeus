from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_mcp_external_transport_runtime.response import no_secret_echo
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.security.credentials import redact_secret_spans

LiveMcpRequestBodyDecision = Literal["materialized", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveMcpRequestBodyResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveMcpRequestBodyDecision
    body_id: Optional[str]
    request_envelope_id: Optional[str]
    server_id: Optional[str]
    tool_name: Optional[str]
    arguments_digest: Optional[str]
    body_ref: Optional[str]
    body_payload: Optional[dict[str, JsonValue]]
    blocked_reasons: tuple[str, ...] = ()
    mcp_envelope_bound: bool = False
    arguments_digest_bound: bool = False
    mcp_request_body_materialized: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    tool_invoked: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveMcpRequestBodyRuntime:
    def materialize(
        self,
        *,
        mcp_envelope: Optional[LiveMcpRequestResult],
        arguments: dict[str, JsonValue],
        body_ref: str,
    ) -> LiveMcpRequestBodyResult:
        safe_ref = _safe_optional(body_ref)
        safe_arguments = _safe_arguments(arguments)
        reasons = list(_envelope_reasons(mcp_envelope))
        digest = _arguments_digest(safe_arguments) if safe_arguments else None
        if mcp_envelope is not None and mcp_envelope.arguments_digest != digest:
            reasons.append("arguments_digest_mismatch")
        if not safe_arguments:
            reasons.append("arguments_required")
        if safe_ref is None:
            reasons.append("body_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                mcp_envelope=mcp_envelope,
                arguments_digest=digest,
                body_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="materialized",
            mcp_envelope=mcp_envelope,
            arguments_digest=digest,
            body_ref=safe_ref,
            body_payload=_body_payload(mcp_envelope, safe_arguments),
            body_id=_body_id(mcp_envelope, safe_ref, safe_arguments),
            mcp_envelope_bound=True,
            arguments_digest_bound=True,
            mcp_request_body_materialized=True,
        )


def _envelope_reasons(mcp_envelope: Optional[LiveMcpRequestResult]) -> tuple[str, ...]:
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
    if mcp_envelope.live_transport_enabled or mcp_envelope.live_production_claimed:
        reasons.append("mcp_envelope_side_effect_detected")
    if not mcp_envelope.no_secret_echo:
        reasons.append("mcp_envelope_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


def _body_payload(mcp_envelope: Optional[LiveMcpRequestResult], arguments: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "jsonrpc": "2.0",
        "id": "" if mcp_envelope is None else mcp_envelope.request_envelope_id,
        "method": "tools/call",
        "params": {
            "server_id": "" if mcp_envelope is None else mcp_envelope.server_id,
            "name": "" if mcp_envelope is None else mcp_envelope.tool_name,
            "arguments": arguments,
        },
    }


def _safe_arguments(arguments: dict[str, JsonValue]) -> dict[str, JsonValue]:
    safe_payload: dict[str, JsonValue] = {}
    for key, value in arguments.items():
        safe_key = redact_secret_spans(str(key))
        safe_payload[safe_key] = redact_secret_spans(value) if isinstance(value, str) else value
    return safe_payload


def _arguments_digest(arguments: dict[str, JsonValue]) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _body_id(mcp_envelope: Optional[LiveMcpRequestResult], body_ref: Optional[str], arguments: dict[str, JsonValue]) -> str:
    payload = {
        "arguments_digest": _arguments_digest(arguments),
        "body_ref": body_ref,
        "request_envelope_id": None if mcp_envelope is None else mcp_envelope.request_envelope_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-mcp-request-body-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _result(
    *,
    decision: LiveMcpRequestBodyDecision,
    mcp_envelope: Optional[LiveMcpRequestResult],
    arguments_digest: Optional[str],
    body_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    body_payload: Optional[dict[str, JsonValue]] = None,
    body_id: Optional[str] = None,
    **flags: bool,
) -> LiveMcpRequestBodyResult:
    result = LiveMcpRequestBodyResult(
        decision=decision,
        body_id=body_id,
        request_envelope_id=None if mcp_envelope is None else mcp_envelope.request_envelope_id,
        server_id=None if mcp_envelope is None else mcp_envelope.server_id,
        tool_name=None if mcp_envelope is None else mcp_envelope.tool_name,
        arguments_digest=arguments_digest,
        body_ref=body_ref,
        body_payload=body_payload,
        blocked_reasons=blocked_reasons,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
