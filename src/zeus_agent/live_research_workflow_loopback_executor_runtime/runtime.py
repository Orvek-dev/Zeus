from __future__ import annotations

import hashlib
import json
from typing import Final, Optional
from urllib.parse import urlparse

from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanResult
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeRuntime
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime.models import (
    LiveResearchWorkflowLoopbackExecutorResult,
)

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "sk-",
    "token=",
    "bearer ",
)


class LiveResearchWorkflowLoopbackExecutorRuntime:
    def execute(
        self,
        *,
        handoff: LiveResearchWorkflowExecutionHandoffResult,
        plan: LiveResearchExecutionPlanResult,
    ) -> LiveResearchWorkflowLoopbackExecutorResult:
        reasons = list(_handoff_reasons(handoff))
        reasons.extend(_plan_reasons(plan))
        if reasons:
            return _blocked(handoff=handoff, plan=plan, reasons=tuple(dict.fromkeys(reasons)))
        smoke = LiveResearchLoopbackSmokeRuntime().execute(plan=plan)
        smoke_reasons = _smoke_reasons(smoke)
        if smoke_reasons:
            return _blocked(
                handoff=handoff,
                plan=plan,
                reasons=tuple(dict.fromkeys(("research_workflow_loopback_executor_smoke_blocked",) + smoke_reasons)),
                smoke=smoke,
            )
        return _executed(handoff=handoff, plan=plan, smoke=smoke)


def _handoff_reasons(handoff: LiveResearchWorkflowExecutionHandoffResult) -> tuple[str, ...]:
    reasons: list[str] = []
    if handoff.decision != "handoff_ready" or not handoff.execution_allowed:
        reasons.append("research_workflow_loopback_executor_handoff_not_ready")
    if handoff.executor_kind != "research":
        reasons.append("research_workflow_loopback_executor_handoff_kind_mismatch")
    if not handoff.no_secret_echo:
        reasons.append("research_workflow_loopback_executor_handoff_secret_echo")
    if _handoff_side_effect_seen(handoff):
        reasons.append("research_workflow_loopback_executor_handoff_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _plan_reasons(plan: LiveResearchExecutionPlanResult) -> tuple[str, ...]:
    reasons: list[str] = []
    if plan.decision != "planned" or not plan.live_search_allowed:
        reasons.append("research_workflow_loopback_executor_plan_not_ready")
    if plan.endpoint is None or not _is_loopback(plan.endpoint):
        reasons.append("research_workflow_loopback_executor_plan_not_loopback")
    if plan.network_opened or plan.client_constructed:
        reasons.append("research_workflow_loopback_executor_plan_side_effect_detected")
    if plan.credential_material_accessed:
        reasons.append("research_workflow_loopback_executor_plan_credential_accessed")
    if plan.live_production_claimed:
        reasons.append("research_workflow_loopback_executor_plan_production_claimed")
    return tuple(dict.fromkeys(reasons))


def _smoke_reasons(smoke: LiveResearchLoopbackSmokeResult) -> tuple[str, ...]:
    reasons: list[str] = []
    if smoke.decision != "smoke_executed":
        reasons.extend(smoke.blocked_reasons)
    if smoke.non_loopback_network_opened:
        reasons.append("research_workflow_loopback_executor_non_loopback_opened")
    if smoke.credential_material_accessed:
        reasons.append("research_workflow_loopback_executor_credential_accessed")
    if smoke.live_production_claimed:
        reasons.append("research_workflow_loopback_executor_production_claimed")
    if not smoke.no_secret_echo:
        reasons.append("research_workflow_loopback_executor_secret_echo")
    return tuple(dict.fromkeys(reasons))


def _handoff_side_effect_seen(handoff: LiveResearchWorkflowExecutionHandoffResult) -> bool:
    return bool(
        handoff.live_transport_enabled
        or handoff.network_opened
        or handoff.credential_material_accessed
        or handoff.raw_secret_returned
        or handoff.live_production_claimed
    )


def _executed(
    *,
    handoff: LiveResearchWorkflowExecutionHandoffResult,
    plan: LiveResearchExecutionPlanResult,
    smoke: LiveResearchLoopbackSmokeResult,
) -> LiveResearchWorkflowLoopbackExecutorResult:
    result = LiveResearchWorkflowLoopbackExecutorResult(
        decision="loopback_executed",
        workflow_execution_id=_execution_id(handoff, plan),
        handoff_manifest_id=handoff.manifest_id,
        handoff_ref=handoff.handoff_ref,
        execution_ref=plan.execution_ref,
        adapter_id=plan.adapter_id,
        source_id=plan.source_id,
        endpoint=plan.endpoint,
        status_code=smoke.status_code,
        latency_ms=smoke.latency_ms,
        result_count=smoke.result_count,
        cleanup_receipt=smoke.cleanup_receipt,
        handoff_bound=True,
        execution_plan_bound=True,
        loopback_smoke_bound=True,
        execution_allowed=True,
        client_constructed=smoke.client_constructed,
        research_invoked=smoke.research_invoked,
        live_transport_enabled=True,
        network_opened=smoke.network_opened,
        non_loopback_network_opened=smoke.non_loopback_network_opened,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _blocked(
    *,
    handoff: LiveResearchWorkflowExecutionHandoffResult,
    plan: LiveResearchExecutionPlanResult,
    reasons: tuple[str, ...],
    smoke: Optional[LiveResearchLoopbackSmokeResult] = None,
) -> LiveResearchWorkflowLoopbackExecutorResult:
    result = LiveResearchWorkflowLoopbackExecutorResult(
        decision="blocked",
        workflow_execution_id=None,
        handoff_manifest_id=handoff.manifest_id,
        handoff_ref=handoff.handoff_ref,
        execution_ref=plan.execution_ref,
        adapter_id=plan.adapter_id,
        source_id=plan.source_id,
        endpoint=plan.endpoint,
        status_code=None if smoke is None else smoke.status_code,
        latency_ms=None if smoke is None else smoke.latency_ms,
        result_count=None if smoke is None else smoke.result_count,
        cleanup_receipt=None if smoke is None else smoke.cleanup_receipt,
        blocked_reasons=reasons,
        handoff_bound=handoff.decision == "handoff_ready",
        execution_plan_bound=plan.decision == "planned",
        loopback_smoke_bound=False if smoke is None else smoke.decision == "smoke_executed",
        execution_allowed=False,
        client_constructed=False if smoke is None else smoke.client_constructed,
        research_invoked=False if smoke is None else smoke.research_invoked,
        live_transport_enabled=False,
        network_opened=False if smoke is None else smoke.network_opened,
        non_loopback_network_opened=False if smoke is None else smoke.non_loopback_network_opened,
        credential_material_accessed=False if smoke is None else smoke.credential_material_accessed,
        live_production_claimed=False if smoke is None else smoke.live_production_claimed,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _execution_id(
    handoff: LiveResearchWorkflowExecutionHandoffResult,
    plan: LiveResearchExecutionPlanResult,
) -> str:
    payload = {"execution_ref": plan.execution_ref, "handoff_manifest_id": handoff.manifest_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-loopback-executor-{0}".format(
        hashlib.sha256(encoded).hexdigest()[:16]
    )


def _is_loopback(endpoint: str) -> bool:
    host = urlparse(endpoint).hostname
    return host in {"127.0.0.1", "localhost", "::1"} if host is not None else False


def _no_secret_echo(result: LiveResearchWorkflowLoopbackExecutorResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
