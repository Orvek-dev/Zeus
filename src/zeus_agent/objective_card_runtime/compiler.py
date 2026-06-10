from __future__ import annotations

from typing import Final, Optional

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.objective_risk_runtime import (
    RiskContext,
    Triage,
    Unknown,
    assess_objective_risk,
)
from zeus_agent.security.credentials import contains_secret_material, redact_secret_spans
from zeus_agent.workflow_fabric_runtime import (
    DecisionRecord,
    NodeKind,
    WorkflowCandidate,
    choose_workflow,
)

from .models import ApprovalStage, CostEstimate, ObjectiveCard

# How many manual approvals a side-effecting node requires before earned
# autonomy relaxes it. Mirrors the "first 3 publishes need approval" UX.
_MANUAL_APPROVALS_BY_EFFECT: Final[dict[SideEffectClass, int]] = {
    SideEffectClass.none: 0,
    SideEffectClass.local_write: 1,
    SideEffectClass.account_write: 3,
    SideEffectClass.public_write: 3,
}


def compile_objective_card(
    *,
    normalized_objective: str,
    triage: Triage,
    unknowns: tuple[Unknown, ...],
    candidates: tuple[WorkflowCandidate, ...],
    required_criteria: tuple[str, ...] = (),
    budget_cap_units: Optional[int] = None,
    projected_runs: Optional[int] = None,
    override_just_do_it: bool = False,
) -> ObjectiveCard:
    """Compile an utterance frame into the rendered objective card.

    Pure: no network, no state writes. The cognitive layer fills ``unknowns`` and
    proposes ``candidates``; Zeus owns the deterministic risk, verification, cost,
    and approval-staging that turn them into a governed, inspectable plan.

    Fail-closed boundaries: an empty objective or raw secret material anywhere in
    the inputs blocks compilation outright — a blocked card carries no plan and
    echoes no secret span.
    """
    if normalized_objective.strip() == "":
        return _blocked_card(
            normalized_objective="[empty-objective]",
            triage=triage,
            decision="blocked_empty_objective",
        )
    if contains_secret_material(_input_corpus(normalized_objective, unknowns, candidates)):
        return _blocked_card(
            normalized_objective=_scrubbed(normalized_objective),
            triage=triage,
            decision="blocked_raw_secret_material",
        )

    risk_profile = assess_objective_risk(
        triage=triage,
        unknowns=unknowns,
        context=RiskContext(budget_cap_units=budget_cap_units),
        override_just_do_it=override_just_do_it,
    )

    decision = choose_workflow(
        candidates,
        required_criteria=required_criteria,
        budget_cap_units=budget_cap_units,
    )
    chosen = _chosen_candidate(candidates, decision.chosen_candidate_id)

    node_ids = tuple(node.node_id for node in chosen.nodes) if chosen is not None else ()
    gaps = (
        tuple(
            node.missing_capability
            for node in chosen.nodes
            if node.kind is NodeKind.gap and node.missing_capability is not None
        )
        if chosen is not None
        else ()
    )
    approval_stages = _approval_stages(chosen)
    cost = _cost_estimate(chosen, budget_cap_units=budget_cap_units, projected_runs=projected_runs)

    overall = _card_decision(
        risk_profile_proceed=risk_profile.proceed_allowed_without_answers,
        has_plan=decision.chosen_candidate_id is not None,
        has_gaps=len(gaps) > 0,
        within_budget=cost.within_budget,
    )

    payload_text = "|".join(
        (
            normalized_objective,
            " ".join(risk_profile.assumptions),
            " ".join(risk_profile.questions),
            " ".join(gaps),
        )
    )
    return ObjectiveCard(
        normalized_objective=normalized_objective.strip(),
        triage=triage,
        decision=overall,
        chosen_workflow_id=decision.chosen_candidate_id,
        workflow_node_ids=node_ids,
        questions=risk_profile.questions,
        assumptions=risk_profile.assumptions,
        capability_gaps=gaps,
        approval_stages=approval_stages,
        cost=cost,
        blocking_question_count=risk_profile.blocking_question_count,
        proceed_allowed_without_answers=risk_profile.proceed_allowed_without_answers,
        decision_record=decision,
        no_secret_echo=not contains_secret_material(payload_text),
    )


def _chosen_candidate(
    candidates: tuple[WorkflowCandidate, ...],
    chosen_id: Optional[str],
) -> Optional[WorkflowCandidate]:
    if chosen_id is None:
        return None
    for candidate in candidates:
        if candidate.candidate_id == chosen_id:
            return candidate
    return None


def _approval_stages(chosen: Optional[WorkflowCandidate]) -> tuple[ApprovalStage, ...]:
    if chosen is None:
        return ()
    stages = [
        ApprovalStage(
            node_id=node.node_id,
            side_effect=node.side_effect.value,
            manual_approvals_remaining=_MANUAL_APPROVALS_BY_EFFECT[node.side_effect],
        )
        for node in chosen.nodes
        if node.side_effect is not SideEffectClass.none
    ]
    return tuple(stages)


def _cost_estimate(
    chosen: Optional[WorkflowCandidate],
    *,
    budget_cap_units: Optional[int],
    projected_runs: Optional[int],
) -> CostEstimate:
    per_run = sum(node.cost_units for node in chosen.nodes) if chosen is not None else 0
    projected_total = None
    if projected_runs is not None:
        projected_total = per_run * projected_runs
    reference_total = projected_total if projected_total is not None else per_run
    within_budget = budget_cap_units is None or reference_total <= budget_cap_units
    return CostEstimate(
        per_run_units=per_run,
        projected_runs=projected_runs,
        projected_total_units=projected_total,
        budget_cap_units=budget_cap_units,
        within_budget=within_budget,
    )


def _card_decision(
    *,
    risk_profile_proceed: bool,
    has_plan: bool,
    has_gaps: bool,
    within_budget: bool,
) -> str:
    """Start is allowed only when there is a verified plan, no open locked
    questions, no unconnected capabilities, and the PROJECTED total cost (not
    just per-run cost) fits the cap."""
    if not has_plan:
        return "blocked_no_verified_workflow"
    if not risk_profile_proceed:
        return "needs_answers"
    if has_gaps:
        return "needs_connections"
    if not within_budget:
        return "over_budget"
    return "ready_to_start"


def _input_corpus(
    normalized_objective: str,
    unknowns: tuple[Unknown, ...],
    candidates: tuple[WorkflowCandidate, ...],
) -> str:
    parts = [normalized_objective]
    parts.extend(unknown.model_dump_json() for unknown in unknowns)
    parts.extend(candidate.model_dump_json() for candidate in candidates)
    return " ".join(parts)


def _scrubbed(raw_value: str) -> str:
    redacted = redact_secret_spans(raw_value.strip())
    if contains_secret_material(redacted):
        return "[redacted-secret]"
    return redacted


def _blocked_card(*, normalized_objective: str, triage: Triage, decision: str) -> ObjectiveCard:
    return ObjectiveCard(
        normalized_objective=normalized_objective,
        triage=triage,
        decision=decision,
        chosen_workflow_id=None,
        workflow_node_ids=(),
        questions=(),
        assumptions=(),
        capability_gaps=(),
        approval_stages=(),
        cost=CostEstimate(per_run_units=0),
        blocking_question_count=0,
        proceed_allowed_without_answers=False,
        decision_record=DecisionRecord(
            chosen_candidate_id=None,
            verdicts=(),
            rejected=(),
            reason=decision,
        ),
        no_secret_echo=not contains_secret_material(normalized_objective),
    )
