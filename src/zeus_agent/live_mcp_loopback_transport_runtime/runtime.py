from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.security.credentials import redact_secret_spans

LiveMcpLoopbackDecision = Literal["executed", "blocked"]
McpTransportKind = Literal["loopback_tool", "remote_server"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_TRANSPORT_KINDS: Final = frozenset(("loopback_tool", "remote_server"))
_CLEANUP_RECEIPT: Final = "mcp-loopback-no-remote-server"
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


class LiveMcpLoopbackTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveMcpLoopbackDecision
    execution_id: Optional[str]
    activation_id: Optional[str]
    adapter_plan_id: Optional[str]
    request_envelope_id: Optional[str]
    transport_kind: Optional[McpTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    transport_activation_bound: bool = False
    adapter_plan_bound: bool = False
    mcp_envelope_bound: bool = False
    loopback_transport: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    tool_invoked: bool = False
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


class LiveMcpLoopbackTransportRuntime:
    def execute(
        self,
        *,
        activation: Optional[LiveTransportActivationResult],
        adapter_plan: LiveMcpAdapterResult,
        mcp_envelope: LiveMcpRequestResult,
        transport_kind: str,
        execution_ref: str,
    ) -> LiveMcpLoopbackTransportResult:
        safe_transport_kind = transport_kind.strip()
        safe_execution_ref = _safe_optional(execution_ref)
        reasons = list(_activation_reasons(activation=activation, adapter_plan=adapter_plan))
        reasons.extend(_adapter_plan_reasons(adapter_plan=adapter_plan, mcp_envelope=mcp_envelope))
        reasons.extend(_mcp_envelope_reasons(mcp_envelope))
        if safe_transport_kind not in _TRANSPORT_KINDS:
            reasons.append("unsupported_mcp_transport_kind")
        if safe_transport_kind == "remote_server":
            reasons.append("mcp_remote_server_not_implemented")
        if safe_execution_ref is None:
            reasons.append("execution_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                activation=activation,
                adapter_plan=adapter_plan,
                mcp_envelope=mcp_envelope,
                transport_kind=safe_transport_kind,
                execution_ref=safe_execution_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="executed",
            activation=activation,
            adapter_plan=adapter_plan,
            mcp_envelope=mcp_envelope,
            transport_kind=safe_transport_kind,
            execution_ref=safe_execution_ref,
            execution_id=_execution_id(
                activation=activation,
                adapter_plan=adapter_plan,
                mcp_envelope=mcp_envelope,
                transport_kind=safe_transport_kind,
                execution_ref=safe_execution_ref,
            ),
            transport_activation_bound=True,
            adapter_plan_bound=True,
            mcp_envelope_bound=True,
            loopback_transport=True,
            tool_invoked=True,
            handler_executed=True,
            live_transport_enabled=True,
            execution_allowed=True,
            response=_loopback_response(mcp_envelope),
        )


def _activation_reasons(
    *,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveMcpAdapterResult,
) -> tuple[str, ...]:
    if activation is None:
        return ("transport_activation_required",)
    reasons = []
    if activation.decision != "activation_ready" or not activation.transport_activation_ready:
        reasons.append("transport_activation_not_ready")
    if activation.adapter_kind != "mcp":
        reasons.append("transport_activation_not_mcp")
    if activation.adapter_plan_id != adapter_plan.adapter_plan_id:
        reasons.append("activation_adapter_plan_mismatch")
    if not activation.live_transport_authorized or activation.live_transport_enabled:
        reasons.append("transport_activation_policy_invalid")
    if activation.network_opened or activation.credential_material_accessed:
        reasons.append("transport_activation_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _adapter_plan_reasons(
    *,
    adapter_plan: LiveMcpAdapterResult,
    mcp_envelope: LiveMcpRequestResult,
) -> tuple[str, ...]:
    reasons = []
    if adapter_plan.decision != "planned" or not adapter_plan.adapter_plan_ready:
        reasons.append("adapter_plan_not_ready")
    if adapter_plan.request_envelope_id != mcp_envelope.request_envelope_id:
        reasons.append("adapter_mcp_envelope_mismatch")
    if adapter_plan.server_started or adapter_plan.tool_invoked or adapter_plan.network_opened:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.resources_enabled or adapter_plan.prompts_enabled:
        reasons.append("adapter_plan_side_effect_detected")
    if adapter_plan.credential_material_accessed or adapter_plan.raw_secret_returned:
        reasons.append("adapter_plan_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _mcp_envelope_reasons(mcp_envelope: LiveMcpRequestResult) -> tuple[str, ...]:
    reasons = []
    if mcp_envelope.decision != "prepared" or not mcp_envelope.request_prepared:
        reasons.append("mcp_envelope_not_prepared")
    if mcp_envelope.server_started or mcp_envelope.tool_invoked or mcp_envelope.network_opened:
        reasons.append("mcp_envelope_side_effect_detected")
    if mcp_envelope.resources_enabled or mcp_envelope.prompts_enabled:
        reasons.append("mcp_envelope_side_effect_detected")
    if mcp_envelope.credential_material_accessed or mcp_envelope.raw_secret_returned:
        reasons.append("mcp_envelope_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    *,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveMcpAdapterResult,
    mcp_envelope: LiveMcpRequestResult,
    transport_kind: str,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "activation_id": None if activation is None else activation.activation_id,
        "adapter_plan_id": adapter_plan.adapter_plan_id,
        "execution_ref": execution_ref,
        "request_envelope_id": mcp_envelope.request_envelope_id,
        "transport_kind": transport_kind,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-mcp-loopback-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _loopback_response(mcp_envelope: LiveMcpRequestResult) -> dict[str, JsonValue]:
    return {
        "mode": "loopback_tool",
        "server_id": mcp_envelope.server_id,
        "tool_name": mcp_envelope.tool_name,
        "arguments_digest": mcp_envelope.arguments_digest,
        "cleanup": _CLEANUP_RECEIPT,
    }


def _result(
    *,
    decision: LiveMcpLoopbackDecision,
    activation: Optional[LiveTransportActivationResult],
    adapter_plan: LiveMcpAdapterResult,
    mcp_envelope: LiveMcpRequestResult,
    transport_kind: str,
    execution_ref: Optional[str],
    execution_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    transport_activation_bound: bool = False,
    adapter_plan_bound: bool = False,
    mcp_envelope_bound: bool = False,
    loopback_transport: bool = False,
    tool_invoked: bool = False,
    handler_executed: bool = False,
    live_transport_enabled: bool = False,
    execution_allowed: bool = False,
    response: Optional[dict[str, JsonValue]] = None,
) -> LiveMcpLoopbackTransportResult:
    kind: Optional[McpTransportKind] = transport_kind if transport_kind in _TRANSPORT_KINDS else None
    result = LiveMcpLoopbackTransportResult(
        decision=decision,
        execution_id=execution_id,
        activation_id=None if activation is None else activation.activation_id,
        adapter_plan_id=adapter_plan.adapter_plan_id,
        request_envelope_id=mcp_envelope.request_envelope_id,
        transport_kind=kind,
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        transport_activation_bound=transport_activation_bound,
        adapter_plan_bound=adapter_plan_bound,
        mcp_envelope_bound=mcp_envelope_bound,
        loopback_transport=loopback_transport,
        tool_invoked=tool_invoked,
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


def _no_secret_echo(result: LiveMcpLoopbackTransportResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
