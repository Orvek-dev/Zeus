from __future__ import annotations

import hashlib
import json

from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleResult
from zeus_agent.live_research_workflow_bundle_status_runtime.models import (
    BundleStatusDecision,
    LiveResearchWorkflowBundleStatusResult,
)


class LiveResearchWorkflowBundleStatusRuntime:
    def build(self, *, bundle: LiveResearchWorkflowBundleResult) -> LiveResearchWorkflowBundleStatusResult:
        blocked_source_count = sum(1 for plan in bundle.source_plans if plan.state == "blocked")
        blocked_reasons = _blocked_reasons(bundle=bundle, blocked_source_count=blocked_source_count)
        decision = _decision(
            bundle=bundle,
            blocked_reasons=blocked_reasons,
            blocked_source_count=blocked_source_count,
        )
        return LiveResearchWorkflowBundleStatusResult(
            decision=decision,
            status_id=_status_id(bundle),
            bundle_id=bundle.bundle_id,
            workflow_plan_id=bundle.workflow_plan_id,
            objective_id=bundle.objective_id,
            source_plan_count=bundle.source_plan_count,
            planned_source_count=bundle.planned_source_count,
            endpoint_required_count=bundle.endpoint_required_count,
            blocked_source_count=blocked_source_count,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(decision),
            network_opened=bundle.network_opened,
            credential_material_accessed=bundle.credential_material_accessed,
            live_production_claimed=bundle.live_production_claimed,
            no_secret_echo=bundle.no_secret_echo and _no_secret_echo(bundle, blocked_reasons),
        )


def _decision(
    *,
    bundle: LiveResearchWorkflowBundleResult,
    blocked_reasons: tuple[str, ...],
    blocked_source_count: int,
) -> BundleStatusDecision:
    hard_blocked = (
        bundle.decision != "bundle_planned"
        or blocked_source_count > 0
        or bundle.network_opened
        or bundle.credential_material_accessed
        or bundle.live_production_claimed
        or not bundle.no_secret_echo
    )
    if hard_blocked:
        return "blocked"
    if bundle.endpoint_required_count > 0:
        return "endpoint_gaps"
    return "bundle_ready"


def _blocked_reasons(
    *,
    bundle: LiveResearchWorkflowBundleResult,
    blocked_source_count: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if bundle.decision != "bundle_planned":
        reasons.append("live_research_workflow_bundle_blocked")
    if blocked_source_count > 0:
        reasons.append("live_research_workflow_bundle_source_blocked")
    if bundle.endpoint_required_count > 0:
        reasons.append("live_research_workflow_bundle_endpoint_gaps")
    if bundle.network_opened or bundle.credential_material_accessed or bundle.live_production_claimed:
        reasons.append("live_research_workflow_bundle_scope_violation")
    if not bundle.no_secret_echo:
        reasons.append("live_research_workflow_bundle_secret_echo")
    for reason in bundle.blocked_reasons:
        reasons.append(reason)
    for source_plan in bundle.source_plans:
        reasons.extend(source_plan.blocked_reasons)
    return tuple(dict.fromkeys(reasons))


def _recommended_next_commands(decision: BundleStatusDecision) -> tuple[str, ...]:
    if decision == "bundle_ready":
        return (
            "zeus live-research-loopback-smoke --plan-json <execution-plan-json> --json",
            "zeus live-research-status --loopback-smoke-result-json <smoke-result-json> --json",
        )
    if decision == "endpoint_gaps":
        return (
            "zeus live-research-workflow --endpoint <source>=<url> --json",
            "zeus live-research-workflow-bundle --workflow-json <workflow-json> --json",
        )
    return ("inspect live_research_workflow_bundle_status blocked_reasons",)


def _status_id(bundle: LiveResearchWorkflowBundleResult) -> str:
    payload = {"bundle_id": bundle.bundle_id, "workflow_plan_id": bundle.workflow_plan_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-bundle-status-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(bundle: LiveResearchWorkflowBundleResult, reasons: tuple[str, ...]) -> bool:
    payload = {"bundle": bundle.model_dump(mode="json"), "reasons": reasons}
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("gh" + "p_", "github_" + "pat_", "sk" + "-", "token" + "=", "bearer" + " ")
    return not any(marker in serialized for marker in markers)
