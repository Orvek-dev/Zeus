from __future__ import annotations

from typing import Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_gateway_delivery_adapter_runtime.models import (
    LiveGatewayDeliveryAdapterReceipt,
    LiveGatewayDeliveryAdapterRequest,
)
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult

_CLEANUP_RECEIPT = "gateway-delivery-adapter-client-closed"


def claim_reasons(claim: Optional[LiveProductionClaimResult]) -> tuple[str, ...]:
    reasons = []
    if claim is None:
        reasons.append("production_claim_required")
        return tuple(reasons)
    if claim.adapter_kind != "gateway":
        reasons.append("gateway_production_claim_mismatch")
    if claim.decision != "production_claim_recorded" or not claim.production_claim_recorded:
        reasons.append("production_claim_not_recorded")
    if not claim.production_claim_authorized or not claim.approval_bound:
        reasons.append("production_claim_not_authorized")
    if claim.claim_id is None or claim.production_approval_id is None:
        reasons.append("production_claim_identity_missing")
    if claim.network_opened or claim.external_delivery_opened:
        reasons.append("production_claim_side_effect_detected")
    if claim.credential_material_accessed or claim.raw_secret_returned or not claim.no_secret_echo:
        reasons.append("production_claim_secret_boundary_failed")
    return tuple(dict.fromkeys(reasons))


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
    claim: Optional[LiveProductionClaimResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    credential_injection: Optional[LiveCredentialInjectionResult],
    gateway_envelope: LiveGatewayDeliveryResult,
) -> Optional[LiveGatewayDeliveryAdapterRequest]:
    if claim is None or claim.claim_id is None or claim.production_approval_id is None:
        return None
    if preflight is None:
        return None
    if credential_injection is None or credential_injection.header_name is None or credential_injection.header_value_ref is None:
        return None
    return LiveGatewayDeliveryAdapterRequest(
        adapter_id=gateway_envelope.adapter_id,
        target=gateway_envelope.target,
        delivery_envelope_id=gateway_envelope.delivery_envelope_id or "",
        production_claim_id=claim.claim_id,
        production_approval_id=claim.production_approval_id,
        header_name=credential_injection.header_name,
        header_value_ref=credential_injection.header_value_ref,
        message_digest=gateway_envelope.message_digest or "",
        idempotency_key=gateway_envelope.idempotency_key,
        timeout_ms=preflight.timeout_ms,
        retry_attempts=preflight.retry_attempts,
    )


def receipt_reasons(receipt: LiveGatewayDeliveryAdapterReceipt) -> tuple[str, ...]:
    reasons = []
    if receipt.status_code < 200 or receipt.status_code >= 300:
        reasons.append("gateway_delivery_adapter_status_not_success")
    if receipt.latency_ms < 0:
        reasons.append("gateway_delivery_adapter_latency_invalid")
    if not receipt.network_opened or not receipt.non_loopback_network_opened:
        reasons.append("gateway_delivery_adapter_network_not_confirmed")
    if not receipt.external_delivery_opened:
        reasons.append("gateway_delivery_adapter_delivery_not_confirmed")
    if receipt.cleanup_receipt != _CLEANUP_RECEIPT:
        reasons.append("gateway_delivery_adapter_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))
