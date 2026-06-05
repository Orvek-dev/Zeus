from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_mcp_external_transport_runtime.response import no_secret_echo, redact_response
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.security.credentials import redact_secret_spans

LiveMcpExternalDecision = Literal["executed", "blocked"]
McpExternalTransportKind = Literal["remote_server"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_CLEANUP_RECEIPT: Final = "mcp-remote-server-client-closed"


class LiveMcpExternalClientResult(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    response_payload: dict[str, JsonValue]
    network_opened: bool = True
    non_loopback_network_opened: bool = True
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    cleanup_receipt: str = _CLEANUP_RECEIPT


class LiveMcpExternalTransportResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveMcpExternalDecision
    execution_id: Optional[str]
    policy_id: Optional[str]
    preflight_id: Optional[str]
    request_envelope_id: Optional[str]
    transport_kind: Optional[McpExternalTransportKind]
    execution_ref: Optional[str]
    cleanup_receipt: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    policy_bound: bool = False
    preflight_bound: bool = False
    mcp_envelope_bound: bool = False
    credential_handoff_bound: bool = False
    remote_executor_preflight_bound: bool = False
    remote_target_bound: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    tool_invoked: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    redacted_response: Optional[dict[str, JsonValue]] = None

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveMcpExternalTransportRuntime:
    def execute(
        self,
        *,
        policy: Optional[LiveRemoteTransportPolicyResult],
        preflight: Optional[LiveRemoteExecutorPreflightResult],
        mcp_envelope: LiveMcpRequestResult,
        client_result: Optional[LiveMcpExternalClientResult],
        execution_ref: str,
    ) -> LiveMcpExternalTransportResult:
        safe_ref = _safe_optional(execution_ref)
        reasons = list(_policy_reasons(policy, mcp_envelope))
        reasons.extend(_preflight_reasons(preflight, policy, mcp_envelope))
        reasons.extend(_mcp_envelope_reasons(mcp_envelope))
        reasons.extend(_client_reasons(client_result))
        if safe_ref is None:
            reasons.append("execution_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                policy=policy,
                preflight=preflight,
                mcp_envelope=mcp_envelope,
                execution_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                client_result=client_result,
            )
        return _result(
            decision="executed",
            policy=policy,
            preflight=preflight,
            mcp_envelope=mcp_envelope,
            execution_ref=safe_ref,
            execution_id=_execution_id(policy, preflight, mcp_envelope, safe_ref),
            client_result=client_result,
            policy_bound=True,
            preflight_bound=True,
            mcp_envelope_bound=True,
            credential_handoff_bound=True,
            remote_executor_preflight_bound=True,
            remote_target_bound=True,
            tool_invoked=True,
            live_transport_enabled=True,
            execution_allowed=True,
            network_opened=True,
            non_loopback_network_opened=True,
            controlled_external_side_effects=True,
            handler_executed=True,
        )


def _policy_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    mcp_envelope: LiveMcpRequestResult,
) -> tuple[str, ...]:
    if policy is None:
        return ("remote_policy_required",)
    reasons = []
    if policy.decision != "policy_ready" or policy.adapter_kind != "mcp":
        reasons.append("mcp_remote_policy_not_ready")
    if policy.remote_target != mcp_envelope.endpoint:
        reasons.append("mcp_remote_target_mismatch")
    if policy.live_transport_enabled or policy.network_opened or policy.handler_executed:
        reasons.append("remote_policy_side_effect_detected")
    if policy.server_started or policy.resources_enabled or policy.prompts_enabled:
        reasons.append("remote_policy_side_effect_detected")
    if policy.credential_material_accessed or policy.raw_secret_returned or not policy.no_secret_echo:
        reasons.append("remote_policy_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _preflight_reasons(
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    mcp_envelope: LiveMcpRequestResult,
) -> tuple[str, ...]:
    if preflight is None:
        return ("remote_executor_preflight_required",)
    reasons = []
    if preflight.decision != "preflight_ready" or preflight.adapter_kind != "mcp":
        reasons.append("mcp_preflight_not_ready")
    if policy is not None and preflight.policy_id != policy.policy_id:
        reasons.append("mcp_preflight_policy_mismatch")
    if preflight.remote_target_identity != mcp_envelope.endpoint_host:
        reasons.append("mcp_preflight_endpoint_mismatch")
    if preflight.network_opened or preflight.live_transport_enabled or preflight.handler_executed:
        reasons.append("mcp_preflight_side_effect_detected")
    if preflight.external_delivery_opened or preflight.raw_secret_returned or not preflight.no_secret_echo:
        reasons.append("mcp_preflight_secret_leak_detected")
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
    if mcp_envelope.live_production_claimed or not mcp_envelope.no_secret_echo:
        reasons.append("mcp_envelope_secret_leak_detected")
    return tuple(dict.fromkeys(reasons))


def _client_reasons(client_result: Optional[LiveMcpExternalClientResult]) -> tuple[str, ...]:
    if client_result is None:
        return ("mcp_external_client_result_required",)
    reasons = []
    if client_result.status_code < 200 or client_result.status_code >= 300:
        reasons.append("mcp_external_http_status_not_success")
    if client_result.latency_ms < 0:
        reasons.append("mcp_external_latency_invalid")
    if not client_result.network_opened or not client_result.non_loopback_network_opened:
        reasons.append("mcp_external_network_not_confirmed")
    if client_result.server_started:
        reasons.append("mcp_external_server_started")
    if client_result.resources_enabled or client_result.prompts_enabled:
        reasons.append("mcp_external_resources_or_prompts_enabled")
    if client_result.cleanup_receipt != _CLEANUP_RECEIPT:
        reasons.append("mcp_external_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _execution_id(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    mcp_envelope: LiveMcpRequestResult,
    execution_ref: Optional[str],
) -> str:
    payload = {
        "execution_ref": execution_ref,
        "policy_id": None if policy is None else policy.policy_id,
        "preflight_id": None if preflight is None else preflight.preflight_id,
        "request_envelope_id": mcp_envelope.request_envelope_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-mcp-external-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveMcpExternalDecision,
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    mcp_envelope: LiveMcpRequestResult,
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    execution_id: Optional[str] = None,
    client_result: Optional[LiveMcpExternalClientResult] = None,
    **flags: bool,
) -> LiveMcpExternalTransportResult:
    redacted = None if client_result is None else redact_response(client_result.response_payload)
    result = LiveMcpExternalTransportResult(
        decision=decision,
        execution_id=execution_id,
        policy_id=None if policy is None else policy.policy_id,
        preflight_id=None if preflight is None else preflight.preflight_id,
        request_envelope_id=mcp_envelope.request_envelope_id,
        transport_kind="remote_server",
        execution_ref=execution_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if flags.get("network_opened") or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        status_code=None if client_result is None else client_result.status_code,
        latency_ms=None if client_result is None else client_result.latency_ms,
        redacted_response=redacted,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
