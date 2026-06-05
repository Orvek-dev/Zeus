from __future__ import annotations

import hashlib
import json
from typing import Final, Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
)
from zeus_agent.live_research_workflow_external_preflight_runtime.models import (
    LiveResearchWorkflowExternalPreflightResult,
    ResearchWorkflowExternalPreflightDecision,
)
from zeus_agent.security.credentials import redact_secret_spans

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "sk-",
    "token=",
    "bearer ",
)


class LiveResearchWorkflowExternalPreflightRuntime:
    def build(
        self,
        *,
        handoff: LiveResearchWorkflowExecutionHandoffResult,
        policy: LiveResearchActivationPolicyResult,
        preflight_ref: str,
        external_execution_ref: str,
        operator_approval_ref: str,
        evidence_ref: str,
    ) -> LiveResearchWorkflowExternalPreflightResult:
        safe_preflight_ref, preflight_secret = _safe_optional(preflight_ref)
        safe_execution_ref, execution_secret = _safe_optional(external_execution_ref)
        safe_approval_ref, approval_secret = _safe_optional(operator_approval_ref)
        safe_evidence_ref, evidence_secret = _safe_optional(evidence_ref)
        reasons = list(
            _input_reasons(
                safe_preflight_ref=safe_preflight_ref,
                safe_execution_ref=safe_execution_ref,
                safe_approval_ref=safe_approval_ref,
                safe_evidence_ref=safe_evidence_ref,
                secret_seen=preflight_secret or execution_secret or approval_secret or evidence_secret,
            )
        )
        reasons.extend(_handoff_reasons(handoff))
        reasons.extend(_policy_reasons(policy, safe_approval_ref))
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: ResearchWorkflowExternalPreflightDecision = (
            "blocked" if blocked_reasons else "external_preflight_ready"
        )
        ready = decision == "external_preflight_ready"
        result = LiveResearchWorkflowExternalPreflightResult(
            decision=decision,
            preflight_id=_preflight_id(handoff, policy, safe_execution_ref) if ready else None,
            preflight_ref=safe_preflight_ref,
            external_execution_ref=safe_execution_ref,
            handoff_manifest_id=handoff.manifest_id,
            handoff_ref=handoff.handoff_ref,
            policy_id=policy.policy_id,
            source_id=policy.source_id,
            source_pin_ref=policy.source_pin_ref,
            operator_approval_ref=safe_approval_ref,
            evidence_ref=safe_evidence_ref,
            blocked_reasons=blocked_reasons,
            workflow_handoff_bound=ready,
            policy_bound=ready,
            approval_bound=safe_approval_ref is not None,
            evidence_bound=safe_evidence_ref is not None,
            source_pin_bound=ready and policy.source_pin_bound,
            live_search_allowed=ready and policy.live_search_allowed,
            execution_allowed=ready and handoff.execution_allowed,
            external_transport_allowed=ready,
            live_transport_enabled=False,
            network_opened=False,
            non_loopback_network_opened=False,
            credential_material_accessed=False,
            raw_secret_returned=False,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _input_reasons(
    *,
    safe_preflight_ref: Optional[str],
    safe_execution_ref: Optional[str],
    safe_approval_ref: Optional[str],
    safe_evidence_ref: Optional[str],
    secret_seen: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if safe_preflight_ref is None:
        reasons.append("preflight_ref_required")
    if safe_execution_ref is None:
        reasons.append("external_execution_ref_required")
    if safe_approval_ref is None:
        reasons.append("operator_approval_ref_required")
    if safe_evidence_ref is None:
        reasons.append("evidence_ref_required")
    if secret_seen:
        reasons.append("secret_like_external_preflight_field")
    return tuple(reasons)


def _handoff_reasons(handoff: LiveResearchWorkflowExecutionHandoffResult) -> tuple[str, ...]:
    reasons: list[str] = []
    if handoff.decision != "handoff_ready" or not handoff.execution_allowed:
        reasons.append("research_workflow_external_handoff_not_ready")
    if handoff.executor_kind != "research":
        reasons.append("research_workflow_external_handoff_kind_mismatch")
    if handoff.live_transport_enabled or handoff.network_opened:
        reasons.append("research_workflow_external_handoff_side_effect_detected")
    if handoff.credential_material_accessed or handoff.raw_secret_returned:
        reasons.append("research_workflow_external_handoff_secret_leak_detected")
    if not handoff.no_secret_echo:
        reasons.append("research_workflow_external_handoff_secret_echo")
    if handoff.live_production_claimed:
        reasons.append("research_workflow_external_handoff_production_claimed")
    return tuple(dict.fromkeys(reasons))


def _policy_reasons(
    policy: LiveResearchActivationPolicyResult,
    approval_ref: Optional[str],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if policy.decision != "activation_planned" or not policy.live_search_allowed:
        reasons.append("research_workflow_external_policy_not_ready")
    if not policy.approval_bound or not policy.source_pin_bound:
        reasons.append("research_workflow_external_policy_controls_missing")
    if approval_ref is not None and policy.approval_ref != approval_ref:
        reasons.append("research_workflow_external_approval_mismatch")
    if policy.network_opened or policy.handler_executed or policy.client_constructed:
        reasons.append("research_workflow_external_policy_side_effect_detected")
    if policy.credential_material_accessed or not policy.no_secret_echo:
        reasons.append("research_workflow_external_policy_secret_leak_detected")
    if policy.live_production_claimed:
        reasons.append("research_workflow_external_policy_production_claimed")
    return tuple(dict.fromkeys(reasons))


def _safe_optional(value: str) -> tuple[Optional[str], bool]:
    redacted = redact_secret_spans(value.strip())
    if redacted == "":
        return None, False
    return redacted, redacted != value.strip()


def _preflight_id(
    handoff: LiveResearchWorkflowExecutionHandoffResult,
    policy: LiveResearchActivationPolicyResult,
    external_execution_ref: Optional[str],
) -> str:
    payload = {
        "external_execution_ref": external_execution_ref,
        "handoff_manifest_id": handoff.manifest_id,
        "policy_id": policy.policy_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-external-preflight-{0}".format(
        hashlib.sha256(encoded).hexdigest()[:16]
    )


def _recommended_next_commands(
    decision: ResearchWorkflowExternalPreflightDecision,
) -> tuple[str, ...]:
    if decision == "external_preflight_ready":
        return (
            "zeus live-research-external-transport --json",
            "zeus live --json",
        )
    return (
        "zeus live-research-workflow-execution-handoff --json",
        "zeus live-research-activation-policy --json",
    )


def _no_secret_echo(result: LiveResearchWorkflowExternalPreflightResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
