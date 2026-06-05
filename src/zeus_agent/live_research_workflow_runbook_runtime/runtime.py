from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewResult
from zeus_agent.live_research_workflow_runbook_runtime.models import (
    LiveResearchWorkflowRunbookResult,
    LiveResearchWorkflowRunbookStep,
    RunbookDecision,
    RunbookStepState,
)


class LiveResearchWorkflowRunbookRuntime:
    def build(
        self,
        *,
        review: LiveResearchWorkflowBundleReviewResult,
        runbook_ref: str,
    ) -> LiveResearchWorkflowRunbookResult:
        decision = _decision(review)
        steps = _steps(review, decision)
        blocked_reasons = review.blocked_reasons if decision == "blocked" else ()
        return LiveResearchWorkflowRunbookResult(
            decision=decision,
            runbook_id=_runbook_id(runbook_ref, review.review_id),
            runbook_ref=runbook_ref,
            review_id=review.review_id,
            review_ref=review.review_ref,
            objective_id=review.objective_id,
            review_decision=review.decision,
            step_count=len(steps),
            steps=steps,
            blocked_reasons=blocked_reasons,
            network_opened=review.network_opened,
            credential_material_accessed=review.credential_material_accessed,
            live_production_claimed=review.live_production_claimed,
            no_secret_echo=review.no_secret_echo and _no_secret_echo(review, steps, blocked_reasons),
        )


def _decision(review: LiveResearchWorkflowBundleReviewResult) -> RunbookDecision:
    if review.decision == "blocked":
        return "blocked"
    if review.network_opened or review.credential_material_accessed or review.live_production_claimed:
        return "blocked"
    if not review.no_secret_echo:
        return "blocked"
    return "runbook_ready"


def _steps(
    review: LiveResearchWorkflowBundleReviewResult,
    decision: RunbookDecision,
) -> tuple[LiveResearchWorkflowRunbookStep, ...]:
    if decision == "blocked":
        return (
            _step(
                index=1,
                state="blocked",
                action="inspect live_research_workflow_runbook blocked_reasons",
                command="inspect live_research_workflow_runbook blocked_reasons",
            ),
        )
    actions = review.required_operator_actions or ("run controlled executor preflight",)
    return tuple(
        _step(
            index=index,
            state="operator_action" if review.decision == "operator_input_required" else "ready",
            action=action,
            command=_recommended_command(action),
        )
        for index, action in enumerate(actions, start=1)
    )


def _step(index: int, state: RunbookStepState, action: str, command: str) -> LiveResearchWorkflowRunbookStep:
    return LiveResearchWorkflowRunbookStep(
        step_id="research-runbook-step-{0}".format(index),
        state=state,
        operator_action=action,
        recommended_command=command,
    )


def _recommended_command(action: str) -> str:
    if "configure missing endpoints" in action:
        return "zeus live-research-workflow --endpoint <source>=<url> --json"
    if "production fetcher" in action:
        return "zeus live-research-workflow-bundle-review --bundle-json <bundle-json> --status-json <status-json> --json"
    if "inspect" in action:
        return "inspect live_research_workflow_runbook blocked_reasons"
    return "zeus live-research-workflow-bundle-review --json"


def _runbook_id(runbook_ref: str, review_id: Optional[str]) -> str:
    payload = {"review_id": review_id, "runbook_ref": runbook_ref}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-runbook-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(
    review: LiveResearchWorkflowBundleReviewResult,
    steps: tuple[LiveResearchWorkflowRunbookStep, ...],
    reasons: tuple[str, ...],
) -> bool:
    payload = {
        "reasons": reasons,
        "review": review.model_dump(mode="json"),
        "steps": [step.model_dump(mode="json") for step in steps],
    }
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("gh" + "p_", "github_" + "pat_", "sk" + "-", "token" + "=", "bearer" + " ")
    return not any(marker in serialized for marker in markers)
