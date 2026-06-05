from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_research_workflow_preflight_plan_runtime.models import (
    LiveResearchWorkflowPreflightCandidate,
    LiveResearchWorkflowPreflightPlanResult,
    PreflightPlanDecision,
)
from zeus_agent.live_research_workflow_runbook_runtime import (
    LiveResearchWorkflowRunbookResult,
    LiveResearchWorkflowRunbookStep,
)


class LiveResearchWorkflowPreflightPlanRuntime:
    def build(
        self,
        *,
        runbook: LiveResearchWorkflowRunbookResult,
        preflight_ref: str,
    ) -> LiveResearchWorkflowPreflightPlanResult:
        operator_action_count = sum(1 for step in runbook.steps if step.state == "operator_action")
        blocked_reasons = _blocked_reasons(runbook, operator_action_count)
        decision = _decision(runbook, operator_action_count, blocked_reasons)
        candidates = _candidates(runbook, preflight_ref, decision)
        return LiveResearchWorkflowPreflightPlanResult(
            decision=decision,
            preflight_plan_id=_plan_id(preflight_ref, runbook.runbook_id),
            preflight_ref=preflight_ref,
            runbook_id=runbook.runbook_id,
            runbook_ref=runbook.runbook_ref,
            objective_id=runbook.objective_id,
            preflight_candidate_count=len(candidates),
            required_operator_action_count=operator_action_count,
            preflight_candidates=candidates,
            blocked_reasons=blocked_reasons,
            network_opened=runbook.network_opened,
            credential_material_accessed=runbook.credential_material_accessed,
            live_production_claimed=runbook.live_production_claimed,
            no_secret_echo=runbook.no_secret_echo and _no_secret_echo(runbook, candidates, blocked_reasons),
        )


def _decision(
    runbook: LiveResearchWorkflowRunbookResult,
    operator_action_count: int,
    blocked_reasons: tuple[str, ...],
) -> PreflightPlanDecision:
    if runbook.decision == "blocked" or runbook.network_opened:
        return "blocked"
    if runbook.credential_material_accessed or runbook.live_production_claimed:
        return "blocked"
    if not runbook.no_secret_echo:
        return "blocked"
    if operator_action_count > 0:
        return "operator_action_required"
    if blocked_reasons:
        return "blocked"
    return "preflight_candidate_ready"


def _blocked_reasons(
    runbook: LiveResearchWorkflowRunbookResult,
    operator_action_count: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if operator_action_count > 0:
        reasons.append("live_research_runbook_operator_action_required")
    reasons.extend(runbook.blocked_reasons)
    if runbook.network_opened:
        reasons.append("live_research_preflight_plan_network_already_opened")
    if runbook.credential_material_accessed:
        reasons.append("live_research_preflight_plan_credential_material_accessed")
    if runbook.live_production_claimed:
        reasons.append("live_research_preflight_plan_production_claimed")
    if not runbook.no_secret_echo:
        reasons.append("live_research_preflight_plan_secret_echo")
    return tuple(dict.fromkeys(reasons))


def _candidates(
    runbook: LiveResearchWorkflowRunbookResult,
    preflight_ref: str,
    decision: PreflightPlanDecision,
) -> tuple[LiveResearchWorkflowPreflightCandidate, ...]:
    if decision != "preflight_candidate_ready":
        return ()
    return tuple(
        _candidate(step, preflight_ref)
        for step in runbook.steps
        if step.state == "ready"
    )


def _candidate(
    step: LiveResearchWorkflowRunbookStep,
    preflight_ref: str,
) -> LiveResearchWorkflowPreflightCandidate:
    return LiveResearchWorkflowPreflightCandidate(
        candidate_id=_candidate_id(preflight_ref, step.step_id),
        executor_kind="research",
        runbook_step_id=step.step_id,
        preflight_ref=preflight_ref,
        recommended_command=step.recommended_command,
    )


def _plan_id(preflight_ref: str, runbook_id: Optional[str]) -> str:
    payload = {"preflight_ref": preflight_ref, "runbook_id": runbook_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-preflight-plan-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _candidate_id(preflight_ref: str, step_id: str) -> str:
    payload = {"preflight_ref": preflight_ref, "step_id": step_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-preflight-candidate-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(
    runbook: LiveResearchWorkflowRunbookResult,
    candidates: tuple[LiveResearchWorkflowPreflightCandidate, ...],
    reasons: tuple[str, ...],
) -> bool:
    payload = {
        "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        "reasons": reasons,
        "runbook": runbook.model_dump(mode="json"),
    }
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("gh" + "p_", "github_" + "pat_", "sk" + "-", "token" + "=", "bearer" + " ")
    return not any(marker in serialized for marker in markers)
