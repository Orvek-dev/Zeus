from __future__ import annotations

from typing import Final, Optional

from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult

ADAPTER_KINDS: Final = frozenset(("provider", "gateway", "mcp"))


def adapter_reasons(adapter_kind: str) -> tuple[str, ...]:
    return () if adapter_kind in ADAPTER_KINDS else ("unsupported_adapter_kind",)


def claim_reasons(adapter_kind: str, claim: Optional[LiveProductionClaimResult]) -> tuple[str, ...]:
    if claim is None:
        return ("production_claim_required",)
    reasons = []
    if claim.adapter_kind != adapter_kind:
        reasons.append("production_claim_adapter_mismatch")
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


def policy_reasons(adapter_kind: str, policy: Optional[LiveRemoteTransportPolicyResult]) -> tuple[str, ...]:
    if policy is None:
        return ("remote_policy_required",)
    reasons = []
    if policy.decision != "policy_ready" or not policy.remote_transport_policy_ready:
        reasons.append("remote_policy_not_ready")
    if policy.adapter_kind != adapter_kind:
        reasons.append("remote_policy_adapter_mismatch")
    if not policy.credential_binding_bound or not policy.remote_target_allowlisted:
        reasons.append("remote_policy_binding_not_ready")
    if policy.network_opened or policy.handler_executed or policy.live_transport_enabled:
        reasons.append("remote_policy_side_effect_detected")
    if policy.credential_material_accessed or policy.raw_secret_returned or not policy.no_secret_echo:
        reasons.append("remote_policy_secret_leak_detected")
    if policy.live_production_claimed:
        reasons.append("remote_policy_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def preflight_reasons(
    adapter_kind: str,
    preflight: Optional[LiveRemoteExecutorPreflightResult],
) -> tuple[str, ...]:
    if preflight is None:
        return ("remote_executor_preflight_required",)
    reasons = []
    if preflight.decision != "preflight_ready" or not preflight.remote_executor_preflight_ready:
        reasons.append("remote_executor_preflight_not_ready")
    if preflight.adapter_kind != adapter_kind:
        reasons.append("remote_executor_preflight_adapter_mismatch")
    if preflight.network_opened or preflight.external_delivery_opened or preflight.live_transport_enabled:
        reasons.append("remote_executor_preflight_side_effect_detected")
    if preflight.credential_material_accessed or preflight.raw_secret_returned or not preflight.no_secret_echo:
        reasons.append("remote_executor_preflight_secret_leak_detected")
    if preflight.live_production_claimed:
        reasons.append("remote_executor_preflight_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def handoff_reasons(
    adapter_kind: str,
    handoff: Optional[LiveRemoteCredentialHandoffResult],
) -> tuple[str, ...]:
    if handoff is None:
        return ("credential_handoff_required",)
    reasons = []
    if handoff.decision != "handoff_ready" or not handoff.credential_handoff_ready:
        reasons.append("credential_handoff_not_ready")
    if handoff.adapter_kind != adapter_kind:
        reasons.append("credential_handoff_adapter_mismatch")
    if handoff.header_name is None or handoff.header_value_ref is None:
        reasons.append("credential_handoff_header_missing")
    if handoff.material_released or handoff.raw_secret_returned or not handoff.no_secret_echo:
        reasons.append("credential_handoff_secret_leak_detected")
    if handoff.network_opened or handoff.external_delivery_opened or handoff.live_transport_enabled:
        reasons.append("credential_handoff_side_effect_detected")
    if handoff.live_production_claimed:
        reasons.append("credential_handoff_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def secret_material_reasons(secret_material: Optional[LiveSecretMaterialResult]) -> tuple[str, ...]:
    if secret_material is None:
        return ("secret_material_required",)
    reasons = []
    if secret_material.decision != "available" or not secret_material.material_available:
        reasons.append("secret_material_not_available")
    if not secret_material.material_proof_id:
        reasons.append("secret_material_proof_required")
    if not secret_material.credential_material_accessed:
        reasons.append("secret_material_access_proof_missing")
    if secret_material.material_released or secret_material.raw_secret_returned:
        reasons.append("secret_material_leak_detected")
    if secret_material.network_opened or secret_material.external_delivery_opened or secret_material.live_transport_enabled:
        reasons.append("secret_material_side_effect_detected")
    if secret_material.live_production_claimed:
        reasons.append("secret_material_production_claim_detected")
    if not secret_material.no_secret_echo:
        reasons.append("secret_material_secret_echo_detected")
    return tuple(dict.fromkeys(reasons))


def binding_reasons(
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    secret_material: Optional[LiveSecretMaterialResult],
) -> tuple[str, ...]:
    reasons = []
    if policy is not None and preflight is not None and preflight.policy_id != policy.policy_id:
        reasons.append("remote_executor_preflight_policy_mismatch")
    if policy is not None and handoff is not None and handoff.policy_id != policy.policy_id:
        reasons.append("credential_handoff_policy_mismatch")
    if preflight is not None and handoff is not None and preflight.handoff_id != handoff.handoff_id:
        reasons.append("remote_executor_preflight_handoff_mismatch")
    if policy is not None and handoff is not None and handoff.remote_target_identity != policy.remote_target_identity:
        reasons.append("credential_handoff_endpoint_mismatch")
    if policy is not None and preflight is not None and preflight.remote_target_identity != policy.remote_target_identity:
        reasons.append("remote_executor_preflight_endpoint_mismatch")
    reasons.extend(_material_binding_reasons(handoff, secret_material))
    return tuple(dict.fromkeys(reasons))


def _material_binding_reasons(
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    secret_material: Optional[LiveSecretMaterialResult],
) -> tuple[str, ...]:
    if handoff is None or secret_material is None:
        return ()
    expected_ref = None
    if secret_material.material_proof_id is not None:
        expected_ref = "secret-proof://{0}".format(secret_material.material_proof_id)
    if handoff.material_proof_id != secret_material.material_proof_id:
        return ("credential_handoff_material_mismatch",)
    if expected_ref is None or handoff.header_value_ref != expected_ref:
        return ("credential_handoff_material_mismatch",)
    if handoff.secret_ref != secret_material.secret_ref:
        return ("credential_handoff_material_mismatch",)
    return ()
