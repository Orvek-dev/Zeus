from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_credential_injection_runtime.models import (
    LiveCredentialInjectionAdapterKind,
    LiveCredentialInjectionDecision,
    LiveCredentialInjectionResult,
)
from zeus_agent.live_credential_injection_runtime.rules import (
    ADAPTER_KINDS,
    adapter_reasons,
    binding_reasons,
    claim_reasons,
    handoff_reasons,
    policy_reasons,
    preflight_reasons,
    secret_material_reasons,
)
from zeus_agent.live_mcp_external_transport_runtime.response import no_secret_echo
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.security.credentials import redact_secret_spans


class LiveCredentialInjectionRuntime:
    def prepare(
        self,
        *,
        adapter_kind: str,
        claim: Optional[LiveProductionClaimResult],
        policy: Optional[LiveRemoteTransportPolicyResult],
        preflight: Optional[LiveRemoteExecutorPreflightResult],
        handoff: Optional[LiveRemoteCredentialHandoffResult],
        secret_material: Optional[LiveSecretMaterialResult],
        injection_ref: str,
    ) -> LiveCredentialInjectionResult:
        safe_kind = adapter_kind.strip()
        safe_ref = _safe_optional(injection_ref)
        reasons = list(adapter_reasons(safe_kind))
        reasons.extend(claim_reasons(safe_kind, claim))
        reasons.extend(policy_reasons(safe_kind, policy))
        reasons.extend(preflight_reasons(safe_kind, preflight))
        reasons.extend(handoff_reasons(safe_kind, handoff))
        reasons.extend(secret_material_reasons(secret_material))
        reasons.extend(binding_reasons(policy, preflight, handoff, secret_material))
        if safe_ref is None:
            reasons.append("injection_ref_required")
        ready = not reasons
        return _result(
            decision="injection_ready" if ready else "blocked",
            adapter_kind=safe_kind,
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            secret_material=secret_material,
            injection_ref=safe_ref,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            ready=ready,
        )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _injection_id(
    *,
    adapter_kind: str,
    claim: Optional[LiveProductionClaimResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    secret_material: Optional[LiveSecretMaterialResult],
    injection_ref: Optional[str],
) -> str:
    payload = {
        "adapter_kind": adapter_kind,
        "claim_id": None if claim is None else claim.claim_id,
        "handoff_id": None if handoff is None else handoff.handoff_id,
        "injection_ref": injection_ref,
        "material_proof_id": None if secret_material is None else secret_material.material_proof_id,
        "policy_id": None if policy is None else policy.policy_id,
        "preflight_id": None if preflight is None else preflight.preflight_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-credential-injection-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveCredentialInjectionDecision,
    adapter_kind: str,
    claim: Optional[LiveProductionClaimResult],
    policy: Optional[LiveRemoteTransportPolicyResult],
    preflight: Optional[LiveRemoteExecutorPreflightResult],
    handoff: Optional[LiveRemoteCredentialHandoffResult],
    secret_material: Optional[LiveSecretMaterialResult],
    injection_ref: Optional[str],
    blocked_reasons: tuple[str, ...],
    ready: bool,
) -> LiveCredentialInjectionResult:
    kind: Optional[LiveCredentialInjectionAdapterKind] = adapter_kind if adapter_kind in ADAPTER_KINDS else None
    result = LiveCredentialInjectionResult(
        decision=decision,
        injection_id=None if not ready else _injection_id(
            adapter_kind=adapter_kind,
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            secret_material=secret_material,
            injection_ref=injection_ref,
        ),
        adapter_kind=kind,
        claim_id=None if claim is None else claim.claim_id,
        production_approval_id=None if claim is None else claim.production_approval_id,
        policy_id=None if policy is None else policy.policy_id,
        preflight_id=None if preflight is None else preflight.preflight_id,
        handoff_id=None if handoff is None else handoff.handoff_id,
        material_proof_id=None if secret_material is None else secret_material.material_proof_id,
        remote_target_identity=None if policy is None else policy.remote_target_identity,
        credential_scope=None if policy is None else policy.credential_scope,
        secret_ref=None if secret_material is None else secret_material.secret_ref,
        injection_ref=injection_ref,
        header_name=None if handoff is None else handoff.header_name,
        header_value_ref=None if handoff is None else handoff.header_value_ref,
        blocked_reasons=blocked_reasons,
        production_claim_bound=ready,
        policy_bound=ready,
        preflight_bound=ready,
        credential_handoff_bound=ready,
        secret_material_bound=ready,
        endpoint_binding_verified=ready,
        material_access_proof_bound=ready,
        sealed_header_ref_ready=ready,
        credential_injection_ready=ready,
        secret_material_env_read_confirmed=False if secret_material is None else secret_material.env_value_read,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
