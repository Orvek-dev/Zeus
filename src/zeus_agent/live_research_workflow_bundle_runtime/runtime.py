from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanRuntime
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigRuntime
from zeus_agent.live_research_workflow_bundle_runtime.models import (
    LiveResearchWorkflowBundleResult,
    LiveResearchWorkflowSourcePlan,
)
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowResult


class LiveResearchWorkflowBundleRuntime:
    def build(self, *, workflow: LiveResearchWorkflowResult, bundle_ref: str) -> LiveResearchWorkflowBundleResult:
        if workflow.decision != "workflow_planned":
            return _blocked(workflow=workflow, bundle_ref=bundle_ref)
        source_plans = tuple(_source_plan(source, bundle_ref) for source in workflow.sources)
        planned_count = sum(1 for plan in source_plans if plan.state == "planned")
        endpoint_required_count = sum(1 for plan in source_plans if plan.state == "endpoint_required")
        return LiveResearchWorkflowBundleResult(
            decision="bundle_planned",
            bundle_id=_bundle_id(bundle_ref, workflow.plan_id),
            bundle_ref=bundle_ref,
            workflow_plan_id=workflow.plan_id,
            objective_id=workflow.objective_id,
            query=workflow.query,
            source_plan_count=len(source_plans),
            planned_source_count=planned_count,
            endpoint_required_count=endpoint_required_count,
            source_plans=source_plans,
            no_secret_echo=_no_secret_echo(source_plans, ()),
        )


def _source_plan(source, bundle_ref: str) -> LiveResearchWorkflowSourcePlan:
    if source.state == "endpoint_required":
        return LiveResearchWorkflowSourcePlan(
            adapter_id=source.adapter_id,
            source_id=source.source_id,
            state="endpoint_required",
            endpoint=source.endpoint,
            blocked_reasons=("live_research_endpoint_required",),
        )
    config = LiveResearchSourceConfigRuntime().configure(
        adapter_id=source.adapter_id,
        endpoint=source.endpoint,
    )
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id=source.source_id,
        query="parallel coding workflow",
        live_search_requested=True,
        approval_ref="approval://research/{0}".format(source.source_id),
        source_pin_ref="source-pin://research/{0}".format(source.source_id),
        max_results=5,
        rate_limit_per_minute=30,
    )
    execution = LiveResearchExecutionPlanRuntime().plan(
        source_config=config,
        policy=policy,
        execution_ref="{0}/{1}".format(bundle_ref.rstrip("/"), source.source_id),
    )
    blocked_reasons = tuple(dict.fromkeys((*config.blocked_reasons, *policy.blocked_reasons, *execution.blocked_reasons)))
    return LiveResearchWorkflowSourcePlan(
        adapter_id=source.adapter_id,
        source_id=source.source_id,
        state="planned" if execution.decision == "planned" else "blocked",
        endpoint=source.endpoint,
        source_config=config,
        activation_policy=policy,
        execution_plan=execution,
        blocked_reasons=blocked_reasons,
    )


def _blocked(*, workflow: LiveResearchWorkflowResult, bundle_ref: str) -> LiveResearchWorkflowBundleResult:
    return LiveResearchWorkflowBundleResult(
        decision="blocked",
        bundle_id=None,
        bundle_ref=bundle_ref,
        workflow_plan_id=workflow.plan_id,
        objective_id=workflow.objective_id,
        query=workflow.query,
        source_plan_count=0,
        planned_source_count=0,
        endpoint_required_count=0,
        source_plans=(),
        blocked_reasons=tuple(dict.fromkeys(("live_research_workflow_not_planned", *workflow.blocked_reasons))),
        no_secret_echo=_no_secret_echo((), workflow.blocked_reasons),
    )


def _bundle_id(bundle_ref: str, workflow_plan_id: Optional[str]) -> str:
    payload = {"bundle_ref": bundle_ref, "workflow_plan_id": workflow_plan_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-bundle-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(source_plans: tuple[LiveResearchWorkflowSourcePlan, ...], reasons: tuple[str, ...]) -> bool:
    payload = {"reasons": reasons, "source_plans": [plan.model_dump(mode="json") for plan in source_plans]}
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("ghp_", "github_pat_", "sk-", "token=", "bearer ")
    return not any(marker in serialized for marker in markers)
