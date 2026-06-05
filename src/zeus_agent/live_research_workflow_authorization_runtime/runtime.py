from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_research_workflow_authorization_runtime.models import (
    LiveResearchWorkflowAuthorizationResult,
    ResearchWorkflowAuthorizationDecision,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import (
    LiveResearchWorkflowPreflightPlanResult,
)
from zeus_agent.security.credentials import redact_secret_spans


class LiveResearchWorkflowAuthorizationRuntime:
    def authorize(
        self,
        *,
        preflight_plan: LiveResearchWorkflowPreflightPlanResult,
        authorization_ref: str,
        operator_approval_ref: str,
        evidence_ref: str,
    ) -> LiveResearchWorkflowAuthorizationResult:
        safe_authorization_ref = _safe_optional(authorization_ref)
        safe_operator_approval_ref = _safe_optional(operator_approval_ref)
        safe_evidence_ref = _safe_optional(evidence_ref)
        reasons = list(_preflight_reasons(preflight_plan))
        reasons.extend(_reference_reasons(safe_authorization_ref, safe_operator_approval_ref, safe_evidence_ref))
        decision = _decision(preflight_plan, tuple(reasons))
        candidate_id = _selected_candidate_id(preflight_plan, decision)
        result = LiveResearchWorkflowAuthorizationResult(
            decision=decision,
            authorization_id=_authorization_id(
                preflight_plan=preflight_plan,
                authorization_ref=safe_authorization_ref,
                operator_approval_ref=safe_operator_approval_ref,
                evidence_ref=safe_evidence_ref,
                decision=decision,
            )
            if decision == "authorization_ready"
            else None,
            authorization_ref=safe_authorization_ref,
            preflight_plan_id=preflight_plan.preflight_plan_id,
            preflight_ref=preflight_plan.preflight_ref,
            objective_id=preflight_plan.objective_id,
            preflight_candidate_count=preflight_plan.preflight_candidate_count,
            authorized_candidate_count=preflight_plan.preflight_candidate_count
            if decision == "authorization_ready"
            else 0,
            selected_candidate_id=candidate_id,
            operator_approval_ref=safe_operator_approval_ref,
            evidence_ref=safe_evidence_ref,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            authorization_envelope_ready=decision == "authorization_ready",
            authorization_bound=decision == "authorization_ready",
            operator_approval_bound=safe_operator_approval_ref is not None and decision == "authorization_ready",
            evidence_bound=safe_evidence_ref is not None and decision == "authorization_ready",
            executor_release_granted=False,
            execution_allowed=False,
            authority_granted=False,
            live_transport_enabled=False,
            network_opened=False,
            credential_material_accessed=False,
            raw_secret_returned=False,
            live_production_claimed=False,
            no_secret_echo=preflight_plan.no_secret_echo,
        )
        return result.model_copy(update={"no_secret_echo": result.no_secret_echo and _no_secret_echo(result)})


def _preflight_reasons(preflight_plan: LiveResearchWorkflowPreflightPlanResult) -> tuple[str, ...]:
    reasons: list[str] = []
    if preflight_plan.decision == "preflight_candidate_ready":
        if preflight_plan.preflight_candidate_count <= 0:
            reasons.append("live_research_preflight_candidate_required")
    elif preflight_plan.decision == "operator_action_required":
        reasons.append("live_research_preflight_plan_operator_action_required")
    else:
        reasons.append("live_research_preflight_plan_blocked")
    reasons.extend(preflight_plan.blocked_reasons)
    if preflight_plan.network_opened:
        reasons.append("live_research_authorization_network_already_opened")
    if preflight_plan.credential_material_accessed:
        reasons.append("live_research_authorization_credential_material_accessed")
    if preflight_plan.live_production_claimed:
        reasons.append("live_research_authorization_production_claimed")
    if not preflight_plan.no_secret_echo:
        reasons.append("live_research_authorization_secret_echo")
    return tuple(dict.fromkeys(reasons))


def _reference_reasons(
    authorization_ref: Optional[str],
    operator_approval_ref: Optional[str],
    evidence_ref: Optional[str],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if authorization_ref is None:
        reasons.append("authorization_ref_required")
    if operator_approval_ref is None:
        reasons.append("operator_approval_ref_required")
    if evidence_ref is None:
        reasons.append("evidence_ref_required")
    return tuple(reasons)


def _decision(
    preflight_plan: LiveResearchWorkflowPreflightPlanResult,
    reasons: tuple[str, ...],
) -> ResearchWorkflowAuthorizationDecision:
    if _hard_block(preflight_plan):
        return "blocked"
    if preflight_plan.decision != "preflight_candidate_ready" or reasons:
        return "operator_action_required"
    return "authorization_ready"


def _hard_block(preflight_plan: LiveResearchWorkflowPreflightPlanResult) -> bool:
    return bool(
        preflight_plan.decision == "blocked"
        or preflight_plan.network_opened
        or preflight_plan.credential_material_accessed
        or preflight_plan.live_production_claimed
        or not preflight_plan.no_secret_echo
    )


def _selected_candidate_id(
    preflight_plan: LiveResearchWorkflowPreflightPlanResult,
    decision: ResearchWorkflowAuthorizationDecision,
) -> Optional[str]:
    if decision != "authorization_ready" or not preflight_plan.preflight_candidates:
        return None
    return preflight_plan.preflight_candidates[0].candidate_id


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    if redacted == "":
        return None
    return redacted


def _authorization_id(
    *,
    preflight_plan: LiveResearchWorkflowPreflightPlanResult,
    authorization_ref: Optional[str],
    operator_approval_ref: Optional[str],
    evidence_ref: Optional[str],
    decision: ResearchWorkflowAuthorizationDecision,
) -> str:
    payload = {
        "authorization_ref": authorization_ref,
        "decision": decision,
        "evidence_ref": evidence_ref,
        "operator_approval_ref": operator_approval_ref,
        "preflight_plan_id": preflight_plan.preflight_plan_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-authorization-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(result: LiveResearchWorkflowAuthorizationResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    markers = ("gh" + "p_", "github_" + "pat_", "sk" + "-", "token" + "=", "bearer" + " ")
    return not any(marker in serialized for marker in markers)
