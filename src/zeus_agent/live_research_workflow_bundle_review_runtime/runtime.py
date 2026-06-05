from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_research_workflow_bundle_review_runtime.models import (
    BundleReviewDecision,
    LiveResearchWorkflowBundleReviewResult,
)
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleResult
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusResult


class LiveResearchWorkflowBundleReviewRuntime:
    def review(
        self,
        *,
        bundle: LiveResearchWorkflowBundleResult,
        status: LiveResearchWorkflowBundleStatusResult,
        review_ref: str,
    ) -> LiveResearchWorkflowBundleReviewResult:
        external_count = (
            0 if status.endpoint_required_count > 0 else _external_review_required_count(bundle)
        )
        mismatch = status.bundle_id != bundle.bundle_id
        blocked_reasons = _blocked_reasons(
            bundle=bundle,
            status=status,
            external_review_required_count=external_count,
            status_mismatch=mismatch,
        )
        decision = _decision(
            status=status,
            blocked_reasons=blocked_reasons,
            external_review_required_count=external_count,
            status_mismatch=mismatch,
        )
        actions = _required_operator_actions(
            decision=decision,
            endpoint_required_count=status.endpoint_required_count,
            external_review_required_count=external_count,
        )
        return LiveResearchWorkflowBundleReviewResult(
            decision=decision,
            review_id=_review_id(review_ref, bundle.bundle_id, status.status_id),
            review_ref=review_ref,
            bundle_id=bundle.bundle_id,
            status_id=status.status_id,
            objective_id=bundle.objective_id,
            source_review_count=bundle.source_plan_count,
            review_ready_source_count=_review_ready_source_count(status, external_count),
            endpoint_required_count=status.endpoint_required_count,
            external_review_required_count=external_count,
            blocked_source_count=status.blocked_source_count,
            blocked_reasons=blocked_reasons,
            required_operator_actions=actions,
            network_opened=bundle.network_opened or status.network_opened,
            credential_material_accessed=bundle.credential_material_accessed or status.credential_material_accessed,
            live_production_claimed=bundle.live_production_claimed or status.live_production_claimed,
            no_secret_echo=bundle.no_secret_echo
            and status.no_secret_echo
            and _no_secret_echo(bundle, status, blocked_reasons, actions),
        )


def _decision(
    *,
    status: LiveResearchWorkflowBundleStatusResult,
    blocked_reasons: tuple[str, ...],
    external_review_required_count: int,
    status_mismatch: bool,
) -> BundleReviewDecision:
    hard_blocked = status.decision == "blocked" or status_mismatch or not status.no_secret_echo
    hard_blocked = hard_blocked or status.network_opened or status.credential_material_accessed
    hard_blocked = hard_blocked or status.live_production_claimed
    if hard_blocked:
        return "blocked"
    if status.decision == "endpoint_gaps" or external_review_required_count > 0:
        return "operator_input_required"
    if blocked_reasons:
        return "operator_input_required"
    return "review_ready"


def _blocked_reasons(
    *,
    bundle: LiveResearchWorkflowBundleResult,
    status: LiveResearchWorkflowBundleStatusResult,
    external_review_required_count: int,
    status_mismatch: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if status_mismatch:
        reasons.append("live_research_workflow_bundle_status_mismatch")
    reasons.extend(status.blocked_reasons)
    if external_review_required_count > 0:
        reasons.append("live_research_external_review_required")
    if bundle.network_opened or status.network_opened:
        reasons.append("live_research_review_network_already_opened")
    if bundle.credential_material_accessed or status.credential_material_accessed:
        reasons.append("live_research_review_credential_material_accessed")
    if bundle.live_production_claimed or status.live_production_claimed:
        reasons.append("live_research_review_production_claimed")
    if not bundle.no_secret_echo or not status.no_secret_echo:
        reasons.append("live_research_review_secret_echo")
    for source_plan in bundle.source_plans:
        reasons.extend(source_plan.blocked_reasons)
    return tuple(dict.fromkeys(reasons))


def _external_review_required_count(bundle: LiveResearchWorkflowBundleResult) -> int:
    count = 0
    for source_plan in bundle.source_plans:
        source_config = source_plan.source_config
        if source_plan.state == "planned" and source_config is not None:
            if source_config.non_loopback_endpoint and not source_config.production_fetcher_configured:
                count += 1
    return count


def _review_ready_source_count(status: LiveResearchWorkflowBundleStatusResult, external_count: int) -> int:
    return max(status.planned_source_count - external_count, 0)


def _required_operator_actions(
    *,
    decision: BundleReviewDecision,
    endpoint_required_count: int,
    external_review_required_count: int,
) -> tuple[str, ...]:
    if decision == "blocked":
        return ("inspect live_research_workflow_bundle_review blocked_reasons",)
    actions: list[str] = []
    if endpoint_required_count > 0:
        actions.append("configure missing endpoints before bundle execution")
    if external_review_required_count > 0:
        actions.append("bind production fetcher, approval, source pins, and audit before non-loopback execution")
    if not actions:
        actions.append("run loopback smoke or controlled executor preflight")
    return tuple(actions)


def _review_id(review_ref: str, bundle_id: Optional[str], status_id: Optional[str]) -> str:
    payload = {"bundle_id": bundle_id, "review_ref": review_ref, "status_id": status_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-bundle-review-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(
    bundle: LiveResearchWorkflowBundleResult,
    status: LiveResearchWorkflowBundleStatusResult,
    reasons: tuple[str, ...],
    actions: tuple[str, ...],
) -> bool:
    payload = {
        "actions": actions,
        "bundle": bundle.model_dump(mode="json"),
        "reasons": reasons,
        "status": status.model_dump(mode="json"),
    }
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("gh" + "p_", "github_" + "pat_", "sk" + "-", "token" + "=", "bearer" + " ")
    return not any(marker in serialized for marker in markers)
