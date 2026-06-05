from __future__ import annotations

import hashlib
import json
from typing import Final, Optional

from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationResult,
)
from zeus_agent.live_research_workflow_execution_handoff_runtime.models import (
    LiveResearchWorkflowExecutionHandoffResult,
    ResearchWorkflowExecutionHandoffDecision,
)
from zeus_agent.live_research_workflow_executor_release_runtime import (
    LiveResearchWorkflowExecutorReleaseResult,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import (
    LiveResearchWorkflowPreflightPlanResult,
)
from zeus_agent.security.credentials import redact_secret_spans

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "gh" + "p_",
    "github_" + "pat_",
    "sk-wave",
    "token" + "=",
    "bearer" + " ",
)


class LiveResearchWorkflowExecutionHandoffRuntime:
    def build(
        self,
        *,
        preflight_plan: LiveResearchWorkflowPreflightPlanResult,
        authorization: LiveResearchWorkflowAuthorizationResult,
        executor_release: LiveResearchWorkflowExecutorReleaseResult,
        handoff_ref: str,
        operator_note: Optional[str] = None,
        production_release_requested: bool = False,
    ) -> LiveResearchWorkflowExecutionHandoffResult:
        safe_ref = _safe_optional(handoff_ref)
        safe_note, note_secret = _safe_optional_note(operator_note)
        reasons = list(_input_reasons(safe_ref, production_release_requested, note_secret))
        reasons.extend(_preflight_reasons(preflight_plan))
        reasons.extend(_authorization_reasons(preflight_plan, authorization))
        reasons.extend(_release_reasons(authorization, executor_release))
        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: ResearchWorkflowExecutionHandoffDecision = (
            "blocked" if blocked_reasons else "handoff_ready"
        )
        selected_candidate_id = authorization.selected_candidate_id
        recommended_command = _recommended_command(preflight_plan, selected_candidate_id)
        ready = decision == "handoff_ready"
        result = LiveResearchWorkflowExecutionHandoffResult(
            decision=decision,
            manifest_id=_manifest_id(preflight_plan, authorization, executor_release, safe_ref) if ready else None,
            handoff_ref=safe_ref,
            preflight_plan_id=preflight_plan.preflight_plan_id,
            authorization_id=authorization.authorization_id,
            release_id=executor_release.release_id,
            objective_id=preflight_plan.objective_id,
            selected_candidate_id=selected_candidate_id if ready else None,
            executor_kind="research",
            release_ref=executor_release.release_ref,
            idempotency_key=executor_release.idempotency_key,
            recommended_command=recommended_command if ready else None,
            blocked_reasons=blocked_reasons,
            operator_note=safe_note,
            preflight_plan_bound=ready,
            authorization_bound=ready,
            executor_release_bound=ready,
            executor_release_granted=ready and executor_release.executor_release_granted,
            execution_allowed=ready and executor_release.execution_allowed,
            authority_granted=False,
            live_transport_enabled=False,
            network_opened=False,
            credential_material_accessed=False,
            raw_secret_returned=False,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _input_reasons(
    handoff_ref: Optional[str],
    production_release_requested: bool,
    note_secret: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if handoff_ref is None:
        reasons.append("handoff_ref_required")
    if production_release_requested:
        reasons.append("production_release_forbidden")
    if note_secret:
        reasons.append("secret_like_handoff_field")
    return tuple(reasons)


def _preflight_reasons(preflight_plan: LiveResearchWorkflowPreflightPlanResult) -> tuple[str, ...]:
    reasons: list[str] = []
    if preflight_plan.decision != "preflight_candidate_ready" or preflight_plan.preflight_candidate_count <= 0:
        reasons.append("research_workflow_handoff_preflight_not_ready")
    if preflight_plan.network_opened:
        reasons.append("research_workflow_handoff_preflight_side_effect_detected")
    if preflight_plan.credential_material_accessed:
        reasons.append("research_workflow_handoff_preflight_side_effect_detected")
    if preflight_plan.live_production_claimed:
        reasons.append("research_workflow_handoff_preflight_production_claimed")
    if not preflight_plan.no_secret_echo:
        reasons.append("research_workflow_handoff_preflight_secret_echo")
    return tuple(dict.fromkeys(reasons))


def _authorization_reasons(
    preflight_plan: LiveResearchWorkflowPreflightPlanResult,
    authorization: LiveResearchWorkflowAuthorizationResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if authorization.decision != "authorization_ready" or not authorization.authorization_envelope_ready:
        reasons.append("research_workflow_handoff_authorization_not_ready")
    if authorization.preflight_plan_id != preflight_plan.preflight_plan_id:
        reasons.append("research_workflow_handoff_authorization_preflight_mismatch")
    if authorization.selected_candidate_id not in _candidate_ids(preflight_plan):
        reasons.append("research_workflow_handoff_candidate_mismatch")
    if not authorization.operator_approval_bound or not authorization.evidence_bound:
        reasons.append("research_workflow_handoff_authorization_incomplete")
    if authorization.executor_release_granted or authorization.execution_allowed:
        reasons.append("research_workflow_handoff_authorization_already_released")
    if _authorization_side_effect_seen(authorization):
        reasons.append("research_workflow_handoff_authorization_side_effect_detected")
    if not authorization.no_secret_echo:
        reasons.append("research_workflow_handoff_authorization_secret_echo")
    return tuple(dict.fromkeys(reasons))


def _release_reasons(
    authorization: LiveResearchWorkflowAuthorizationResult,
    executor_release: LiveResearchWorkflowExecutorReleaseResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if executor_release.decision != "release_ready" or not executor_release.release_envelope_ready:
        reasons.append("research_workflow_handoff_executor_release_not_ready")
    if not executor_release.executor_release_granted or not executor_release.execution_allowed:
        reasons.append("research_workflow_handoff_executor_release_not_ready")
    if executor_release.authorization_id != authorization.authorization_id:
        reasons.append("research_workflow_handoff_release_authorization_mismatch")
    if executor_release.selected_candidate_id != authorization.selected_candidate_id:
        reasons.append("research_workflow_handoff_release_candidate_mismatch")
    if _release_side_effect_seen(executor_release):
        reasons.append("research_workflow_handoff_executor_release_side_effect_detected")
    if not executor_release.no_secret_echo:
        reasons.append("research_workflow_handoff_executor_release_secret_echo")
    return tuple(dict.fromkeys(reasons))


def _authorization_side_effect_seen(authorization: LiveResearchWorkflowAuthorizationResult) -> bool:
    return bool(
        authorization.network_opened
        or authorization.credential_material_accessed
        or authorization.raw_secret_returned
        or authorization.live_transport_enabled
        or authorization.live_production_claimed
    )


def _release_side_effect_seen(executor_release: LiveResearchWorkflowExecutorReleaseResult) -> bool:
    return bool(
        executor_release.network_opened
        or executor_release.credential_material_accessed
        or executor_release.raw_secret_returned
        or executor_release.live_transport_enabled
        or executor_release.live_production_claimed
    )


def _candidate_ids(preflight_plan: LiveResearchWorkflowPreflightPlanResult) -> tuple[str, ...]:
    return tuple(candidate.candidate_id for candidate in preflight_plan.preflight_candidates)


def _recommended_command(
    preflight_plan: LiveResearchWorkflowPreflightPlanResult,
    candidate_id: Optional[str],
) -> Optional[str]:
    for candidate in preflight_plan.preflight_candidates:
        if candidate.candidate_id == candidate_id:
            return candidate.recommended_command
    return None


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    if redacted == "":
        return None
    return redacted


def _safe_optional_note(value: Optional[str]) -> tuple[Optional[str], bool]:
    if value is None:
        return None, False
    redacted = redact_secret_spans(value.strip())
    return redacted, redacted != value.strip()


def _manifest_id(
    preflight_plan: LiveResearchWorkflowPreflightPlanResult,
    authorization: LiveResearchWorkflowAuthorizationResult,
    executor_release: LiveResearchWorkflowExecutorReleaseResult,
    handoff_ref: Optional[str],
) -> str:
    payload = {
        "authorization_id": authorization.authorization_id,
        "handoff_ref": handoff_ref,
        "preflight_plan_id": preflight_plan.preflight_plan_id,
        "release_id": executor_release.release_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-execution-handoff-{0}".format(
        hashlib.sha256(encoded).hexdigest()[:16]
    )


def _recommended_next_commands(decision: ResearchWorkflowExecutionHandoffDecision) -> tuple[str, ...]:
    if decision == "handoff_ready":
        return (
            "review research workflow execution handoff",
            "zeus live --json",
            "prepare research workflow transport executor",
        )
    return (
        "zeus live-research-workflow-preflight-plan --json",
        "zeus live-research-workflow-authorization --json",
        "zeus live-research-workflow-executor-release --json",
    )


def _no_secret_echo(result: LiveResearchWorkflowExecutionHandoffResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
