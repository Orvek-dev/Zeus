from __future__ import annotations

from typing import Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult


def credential_injection_reasons(
    *,
    adapter_kind: str,
    claim: Optional[LiveProductionClaimResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    credential_injection: Optional[LiveCredentialInjectionResult],
) -> tuple[str, ...]:
    if credential_injection is None:
        return ("credential_injection_required",)
    reasons = list(_injection_state_reasons(adapter_kind, credential_injection))
    reasons.extend(_claim_binding_reasons(claim, credential_injection))
    reasons.extend(_policy_binding_reasons(policy, credential_injection))
    reasons.extend(_preflight_binding_reasons(preflight, credential_injection))
    reasons.extend(_handoff_binding_reasons(handoff, credential_injection))
    return tuple(dict.fromkeys(reasons))


def _injection_state_reasons(adapter_kind: str, injection: LiveCredentialInjectionResult) -> tuple[str, ...]:
    reasons = []
    if injection.decision != "injection_ready" or not injection.credential_injection_ready:
        reasons.append("credential_injection_not_ready")
    if injection.adapter_kind != adapter_kind:
        reasons.append("credential_injection_adapter_mismatch")
    if not injection.sealed_header_ref_ready or injection.header_name is None or injection.header_value_ref is None:
        reasons.append("credential_injection_header_missing")
    if injection.credential_material_accessed or injection.material_released or injection.raw_secret_returned:
        reasons.append("credential_injection_secret_boundary_failed")
    if not injection.no_secret_echo:
        reasons.append("credential_injection_secret_boundary_failed")
    if injection.network_opened or injection.external_delivery_opened or injection.live_transport_enabled:
        reasons.append("credential_injection_side_effect_detected")
    if injection.execution_allowed or injection.live_production_claimed:
        reasons.append("credential_injection_side_effect_detected")
    if injection.server_started or injection.resources_enabled or injection.prompts_enabled:
        reasons.append("credential_injection_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _claim_binding_reasons(
    claim: Optional[LiveProductionClaimResult],
    injection: LiveCredentialInjectionResult,
) -> tuple[str, ...]:
    if claim is None:
        return ()
    if injection.claim_id != claim.claim_id or injection.production_approval_id != claim.production_approval_id:
        return ("credential_injection_claim_mismatch",)
    return ()


def _policy_binding_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    injection: LiveCredentialInjectionResult,
) -> tuple[str, ...]:
    if policy is None:
        return ()
    if injection.policy_id != policy.policy_id:
        return ("credential_injection_policy_mismatch",)
    if injection.remote_target_identity != policy.remote_target_identity:
        return ("credential_injection_endpoint_mismatch",)
    return ()


def _preflight_binding_reasons(
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    injection: LiveCredentialInjectionResult,
) -> tuple[str, ...]:
    if preflight is None:
        return ()
    if injection.preflight_id != preflight.preflight_id:
        return ("credential_injection_preflight_mismatch",)
    return ()


def _handoff_binding_reasons(
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    injection: LiveCredentialInjectionResult,
) -> tuple[str, ...]:
    if handoff is None:
        return ()
    if injection.handoff_id != handoff.handoff_id:
        return ("credential_injection_handoff_mismatch",)
    if injection.header_name != handoff.header_name or injection.header_value_ref != handoff.header_value_ref:
        return ("credential_injection_header_mismatch",)
    return ()
