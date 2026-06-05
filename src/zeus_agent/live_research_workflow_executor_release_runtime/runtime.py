from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationResult,
)
from zeus_agent.live_research_workflow_executor_release_runtime.models import (
    LiveResearchWorkflowExecutorReleaseResult,
)
from zeus_agent.security.credentials import redact_secret_spans


class LiveResearchWorkflowExecutorReleaseRuntime:
    def release(
        self,
        *,
        authorization: Optional[LiveResearchWorkflowAuthorizationResult],
        release_ref: str,
        idempotency_key: str,
    ) -> LiveResearchWorkflowExecutorReleaseResult:
        safe_release_ref = _safe_optional(release_ref)
        safe_idempotency_key = redact_secret_spans(idempotency_key.strip())
        reasons = list(_authorization_reasons(authorization))
        if safe_release_ref is None:
            reasons.append("release_ref_required")
        if safe_idempotency_key == "":
            reasons.append("idempotency_key_required")
        if reasons:
            return _result(
                decision="blocked",
                authorization=authorization,
                release_ref=safe_release_ref,
                idempotency_key=safe_idempotency_key,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="release_ready",
            authorization=authorization,
            release_ref=safe_release_ref,
            idempotency_key=safe_idempotency_key,
            release_id=_release_id(
                authorization=authorization,
                release_ref=safe_release_ref,
                idempotency_key=safe_idempotency_key,
            ),
            release_envelope_ready=True,
            executor_release_granted=True,
            execution_allowed=True,
        )


def _authorization_reasons(
    authorization: Optional[LiveResearchWorkflowAuthorizationResult],
) -> tuple[str, ...]:
    if authorization is None:
        return ("research_workflow_authorization_required",)
    reasons: list[str] = []
    if authorization.decision != "authorization_ready" or not authorization.authorization_envelope_ready:
        reasons.append("research_workflow_authorization_not_ready")
    if not authorization.operator_approval_bound or not authorization.evidence_bound:
        reasons.append("research_workflow_authorization_incomplete")
    if authorization.authorized_candidate_count <= 0 or authorization.selected_candidate_id is None:
        reasons.append("research_workflow_authorized_candidate_required")
    if authorization.executor_release_granted or authorization.execution_allowed:
        reasons.append("research_workflow_authorization_already_released")
    if _authorization_side_effect_seen(authorization):
        reasons.append("research_workflow_authorization_side_effect_detected")
    if not authorization.no_secret_echo:
        reasons.append("research_workflow_authorization_secret_echo")
    return tuple(dict.fromkeys(reasons))


def _authorization_side_effect_seen(authorization: LiveResearchWorkflowAuthorizationResult) -> bool:
    return bool(
        authorization.network_opened
        or authorization.credential_material_accessed
        or authorization.raw_secret_returned
        or authorization.live_transport_enabled
        or authorization.live_production_claimed
    )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    if redacted == "":
        return None
    return redacted


def _release_id(
    *,
    authorization: Optional[LiveResearchWorkflowAuthorizationResult],
    release_ref: Optional[str],
    idempotency_key: str,
) -> str:
    payload = {
        "authorization_id": None if authorization is None else authorization.authorization_id,
        "idempotency_key": idempotency_key,
        "release_ref": release_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-executor-release-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: str,
    authorization: Optional[LiveResearchWorkflowAuthorizationResult],
    release_ref: Optional[str],
    idempotency_key: str,
    release_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    release_envelope_ready: bool = False,
    executor_release_granted: bool = False,
    execution_allowed: bool = False,
) -> LiveResearchWorkflowExecutorReleaseResult:
    result = LiveResearchWorkflowExecutorReleaseResult(
        decision=decision,
        release_id=release_id,
        authorization_id=None if authorization is None else authorization.authorization_id,
        authorization_ref=None if authorization is None else authorization.authorization_ref,
        selected_candidate_id=None if authorization is None else authorization.selected_candidate_id,
        executor_kind="research",
        release_ref=release_ref,
        idempotency_key=idempotency_key,
        blocked_reasons=blocked_reasons,
        release_envelope_ready=release_envelope_ready,
        executor_release_granted=executor_release_granted,
        execution_allowed=execution_allowed,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveResearchWorkflowExecutorReleaseResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    markers = ("gh" + "p_", "github_" + "pat_", "sk" + "-", "token" + "=", "bearer" + " ")
    return not any(marker in serialized for marker in markers)
