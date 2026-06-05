from __future__ import annotations

from typing import Optional

from zeus_agent.live_mcp_owned_client_transport_runtime.models import (
    LiveMcpOwnedClientReceipt,
    LiveMcpOwnedClientRequest,
)
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult

_CLEANUP_RECEIPT = "mcp-owned-client-closed"


def preflight_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    mcp_envelope: LiveMcpRequestResult,
) -> tuple[str, ...]:
    reasons = []
    if policy is None:
        reasons.append("remote_policy_required")
    elif policy.decision != "policy_ready" or policy.adapter_kind != "mcp":
        reasons.append("mcp_remote_policy_not_ready")
    if preflight is None:
        reasons.append("remote_executor_preflight_required")
    elif preflight.decision != "preflight_ready" or preflight.adapter_kind != "mcp":
        reasons.append("mcp_preflight_not_ready")
    if handoff is None:
        reasons.append("credential_handoff_required")
    elif handoff.decision != "handoff_ready" or handoff.adapter_kind != "mcp":
        reasons.append("mcp_handoff_not_ready")
    reasons.extend(binding_reasons(policy, preflight, handoff, mcp_envelope))
    return tuple(dict.fromkeys(reasons))


def binding_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    mcp_envelope: LiveMcpRequestResult,
) -> tuple[str, ...]:
    reasons = []
    if policy is not None and policy.remote_target != mcp_envelope.endpoint:
        reasons.append("mcp_remote_target_mismatch")
    if preflight is not None and preflight.remote_target_identity != mcp_envelope.endpoint_host:
        reasons.append("mcp_preflight_endpoint_mismatch")
    if policy is not None and preflight is not None and preflight.policy_id != policy.policy_id:
        reasons.append("mcp_preflight_policy_mismatch")
    if handoff is not None and policy is not None and handoff.policy_id != policy.policy_id:
        reasons.append("mcp_handoff_policy_mismatch")
    if handoff is not None and (handoff.header_name is None or handoff.header_value_ref is None):
        reasons.append("mcp_handoff_header_missing")
    if mcp_envelope.decision != "prepared" or not mcp_envelope.request_prepared:
        reasons.append("mcp_envelope_not_prepared")
    if not mcp_envelope.tool_allowlisted:
        reasons.append("mcp_tool_not_allowlisted")
    return tuple(dict.fromkeys(reasons))


def client_request(
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    mcp_envelope: LiveMcpRequestResult,
) -> Optional[LiveMcpOwnedClientRequest]:
    if preflight is None or handoff is None or handoff.header_name is None or handoff.header_value_ref is None:
        return None
    if mcp_envelope.endpoint_host is None:
        return None
    return LiveMcpOwnedClientRequest(
        server_id=mcp_envelope.server_id,
        tool_name=mcp_envelope.tool_name,
        endpoint=mcp_envelope.endpoint,
        endpoint_host=mcp_envelope.endpoint_host,
        request_envelope_id=mcp_envelope.request_envelope_id or "",
        header_name=handoff.header_name,
        header_value_ref=handoff.header_value_ref,
        arguments_digest=mcp_envelope.arguments_digest or "",
        timeout_ms=preflight.timeout_ms,
        retry_attempts=preflight.retry_attempts,
    )


def receipt_reasons(receipt: LiveMcpOwnedClientReceipt) -> tuple[str, ...]:
    reasons = []
    if receipt.status_code < 200 or receipt.status_code >= 300:
        reasons.append("mcp_owned_client_status_not_success")
    if receipt.latency_ms < 0:
        reasons.append("mcp_owned_client_latency_invalid")
    if not receipt.network_opened or not receipt.non_loopback_network_opened:
        reasons.append("mcp_owned_client_network_not_confirmed")
    if receipt.server_started:
        reasons.append("mcp_owned_client_server_started")
    if receipt.resources_enabled or receipt.prompts_enabled:
        reasons.append("mcp_owned_client_resources_or_prompts_enabled")
    if receipt.cleanup_receipt != _CLEANUP_RECEIPT:
        reasons.append("mcp_owned_client_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))
