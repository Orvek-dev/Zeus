from __future__ import annotations

from typing import Optional

from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_gateway_owned_client_transport_runtime.models import (
    LiveGatewayOwnedClientReceipt,
    LiveGatewayOwnedClientRequest,
)
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult

_CLEANUP_RECEIPT = "gateway-owned-client-closed"


def preflight_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    gateway_envelope: LiveGatewayDeliveryResult,
) -> tuple[str, ...]:
    reasons = []
    if policy is None:
        reasons.append("remote_policy_required")
    elif policy.decision != "policy_ready" or policy.adapter_kind != "gateway":
        reasons.append("gateway_remote_policy_not_ready")
    if preflight is None:
        reasons.append("remote_executor_preflight_required")
    elif preflight.decision != "preflight_ready" or preflight.adapter_kind != "gateway":
        reasons.append("gateway_preflight_not_ready")
    if handoff is None:
        reasons.append("credential_handoff_required")
    elif handoff.decision != "handoff_ready" or handoff.adapter_kind != "gateway":
        reasons.append("gateway_handoff_not_ready")
    reasons.extend(binding_reasons(policy, preflight, handoff, gateway_envelope))
    return tuple(dict.fromkeys(reasons))


def binding_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    gateway_envelope: LiveGatewayDeliveryResult,
) -> tuple[str, ...]:
    reasons = []
    if policy is not None and policy.remote_target != gateway_envelope.target:
        reasons.append("gateway_remote_target_mismatch")
    if preflight is not None and preflight.remote_target_identity != gateway_envelope.target:
        reasons.append("gateway_preflight_target_mismatch")
    if policy is not None and preflight is not None and preflight.policy_id != policy.policy_id:
        reasons.append("gateway_preflight_policy_mismatch")
    if handoff is not None and policy is not None and handoff.policy_id != policy.policy_id:
        reasons.append("gateway_handoff_policy_mismatch")
    if handoff is not None and (handoff.header_name is None or handoff.header_value_ref is None):
        reasons.append("gateway_handoff_header_missing")
    if gateway_envelope.decision != "prepared" or not gateway_envelope.delivery_prepared:
        reasons.append("gateway_envelope_not_prepared")
    if not gateway_envelope.delivery_target_allowlisted:
        reasons.append("gateway_target_not_allowlisted")
    return tuple(dict.fromkeys(reasons))


def client_request(
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    gateway_envelope: LiveGatewayDeliveryResult,
) -> Optional[LiveGatewayOwnedClientRequest]:
    if preflight is None or handoff is None or handoff.header_name is None or handoff.header_value_ref is None:
        return None
    return LiveGatewayOwnedClientRequest(
        adapter_id=gateway_envelope.adapter_id,
        target=gateway_envelope.target,
        delivery_envelope_id=gateway_envelope.delivery_envelope_id or "",
        header_name=handoff.header_name,
        header_value_ref=handoff.header_value_ref,
        message_digest=gateway_envelope.message_digest or "",
        idempotency_key=gateway_envelope.idempotency_key,
        timeout_ms=preflight.timeout_ms,
        retry_attempts=preflight.retry_attempts,
    )


def receipt_reasons(receipt: LiveGatewayOwnedClientReceipt) -> tuple[str, ...]:
    reasons = []
    if receipt.status_code < 200 or receipt.status_code >= 300:
        reasons.append("gateway_owned_client_status_not_success")
    if receipt.latency_ms < 0:
        reasons.append("gateway_owned_client_latency_invalid")
    if not receipt.network_opened or not receipt.non_loopback_network_opened:
        reasons.append("gateway_owned_client_network_not_confirmed")
    if not receipt.external_delivery_opened:
        reasons.append("gateway_owned_client_delivery_not_confirmed")
    if receipt.cleanup_receipt != _CLEANUP_RECEIPT:
        reasons.append("gateway_owned_client_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))
