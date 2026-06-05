from __future__ import annotations

from typing import Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalClientResult
from zeus_agent.live_research_owned_client_transport_runtime.models import (
    LiveResearchOwnedClientReceipt,
    LiveResearchOwnedClientRequest,
)

_OWNED_CLEANUP_RECEIPT = "research-owned-client-closed"
_EXTERNAL_CLEANUP_RECEIPT = "research-external-client-closed"


def policy_reasons(policy: Optional[LiveResearchActivationPolicyResult]) -> tuple[str, ...]:
    if policy is None:
        return ("live_research_policy_required",)
    reasons = []
    if policy.decision != "activation_planned" or not policy.live_search_allowed:
        reasons.append("live_research_policy_not_activation_planned")
    if not policy.approval_bound or not policy.source_pin_bound:
        reasons.append("live_research_policy_missing_controls")
    if policy.network_opened or policy.handler_executed or policy.client_constructed:
        reasons.append("live_research_policy_side_effect_detected")
    if policy.credential_material_accessed or not policy.no_secret_echo:
        reasons.append("live_research_policy_secret_leak_detected")
    if policy.live_production_claimed:
        reasons.append("live_research_policy_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def client_request(policy: Optional[LiveResearchActivationPolicyResult]) -> Optional[LiveResearchOwnedClientRequest]:
    if policy is None or policy.policy_id is None or policy.source_pin_ref is None:
        return None
    return LiveResearchOwnedClientRequest(
        policy_id=policy.policy_id,
        source_id=policy.source_id,
        query=policy.query,
        source_pin_ref=policy.source_pin_ref,
        max_results=policy.max_results,
        rate_limit_per_minute=policy.rate_limit_per_minute,
    )


def receipt_reasons(
    policy: Optional[LiveResearchActivationPolicyResult],
    receipt: LiveResearchOwnedClientReceipt,
) -> tuple[str, ...]:
    reasons = []
    if receipt.status_code < 200 or receipt.status_code >= 300:
        reasons.append("research_owned_client_status_not_success")
    if receipt.latency_ms < 0:
        reasons.append("research_owned_client_latency_invalid")
    if receipt.result_count < 0:
        reasons.append("research_owned_client_result_count_invalid")
    if policy is not None and receipt.result_count > policy.max_results:
        reasons.append("research_owned_client_result_count_exceeded")
    if policy is not None and receipt.source_pin_ref != policy.source_pin_ref:
        reasons.append("research_source_pin_mismatch")
    if not receipt.network_opened or not receipt.non_loopback_network_opened:
        reasons.append("research_owned_client_network_not_confirmed")
    if receipt.cleanup_receipt != _OWNED_CLEANUP_RECEIPT:
        reasons.append("research_owned_client_cleanup_receipt_invalid")
    return tuple(dict.fromkeys(reasons))


def external_client_result(receipt: LiveResearchOwnedClientReceipt) -> LiveResearchExternalClientResult:
    return LiveResearchExternalClientResult(
        status_code=receipt.status_code,
        latency_ms=receipt.latency_ms,
        source_pin_ref=receipt.source_pin_ref,
        result_count=receipt.result_count,
        response_payload=receipt.response_payload,
        network_opened=receipt.network_opened,
        non_loopback_network_opened=receipt.non_loopback_network_opened,
        cleanup_receipt=_EXTERNAL_CLEANUP_RECEIPT,
    )
