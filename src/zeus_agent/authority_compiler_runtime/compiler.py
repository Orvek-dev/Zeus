from __future__ import annotations

from datetime import datetime
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict

from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStore,
    SideEffectClass,
)
from zeus_agent.objective_card_runtime import ObjectiveFrameInput
from zeus_agent.objective_risk_runtime import Resolution, RiskContext, assess_objective_risk
from zeus_agent.trust_loop_runtime import Reversibility
from zeus_agent.workflow_fabric_runtime import NodeKind, WorkflowCandidate

from .models import (
    AuthorityEnvelope,
    CapabilityRequest,
    GrantTier,
    GrantedCapability,
    LockedCapability,
    VoiQuestion,
    require_text,
)

_DANGEROUS_SIDE_EFFECTS: Final[frozenset[SideEffectClass]] = frozenset(
    {SideEffectClass.account_write, SideEffectClass.public_write}
)


class ExcludedCapability(BaseModel):
    """A capability the candidate mentioned but the closure could not trace.

    Exclusion is the compiler's core guarantee: anything that does not trace
    to a frame clause never enters the envelope, so opportunistic scope
    ("하는 김에") cannot be granted by accident.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    node_id: str
    reason: str


class ShrinkProposal(BaseModel):
    """Step 8 output: next-time scope = granted ∩ actually-used."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    kept: tuple[str, ...] = ()
    dropped: tuple[str, ...] = ()


class CompileResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    envelope: AuthorityEnvelope
    requests: tuple[CapabilityRequest, ...] = ()
    excluded: tuple[ExcludedCapability, ...] = ()
    proceed_allowed_without_answers: bool = True


def compile_envelope(
    *,
    frame: ObjectiveFrameInput,
    objective_id: str,
    principal_id: str,
    capabilities: CapabilityStore,
    candidate_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> CompileResult:
    """The least-authority compiler: frame in, AuthorityEnvelope out.

    Step 1 (intent parse) happens at the LLM boundary — ``frame`` IS its
    validated output. Steps 2-7 run here, deterministically. Step 8 (burn and
    usage shrink) closes the loop after execution via ``shrink_proposal``.
    """
    objective = require_text(objective_id, "objective_id")
    principal = require_text(principal_id, "principal_id")
    candidate = _select_candidate(frame, candidate_id)

    # 2. capability resolution: candidate nodes → capability requests.
    requests, unresolved = _resolve_requests(candidate, capabilities)

    # 3. dependency-closure provenance: untraced requests are EXCLUDED.
    traced_ids = _dependency_closure(candidate, frame)
    traced_requests: list[CapabilityRequest] = []
    excluded: list[ExcludedCapability] = list(unresolved)
    for request in requests:
        if request.derived_from in traced_ids:
            traced_requests.append(request)
        else:
            excluded.append(
                ExcludedCapability(
                    capability_id=request.capability_id,
                    node_id=request.derived_from,
                    reason="untraced_to_frame_clause",
                )
            )

    # 4-6. risk partition into tiers + taint overlay, per granted capability.
    granted = tuple(
        _grant_for(request, capabilities.get(request.capability_id))
        for request in traced_requests
    )

    # 5. lock list: dangerous same-verb siblings that were NOT derived.
    lock_list = _lock_list(granted, capabilities)

    # 7. VoI questions: ask only where expected damage clears the triage bar.
    profile = assess_objective_risk(
        triage=frame.triage,
        unknowns=frame.unknowns,
        context=RiskContext(
            projected_cost_units=sum(node.cost_units for node in candidate.nodes),
            budget_cap_units=frame.budget_cap_units,
        ),
        override_just_do_it=frame.override_just_do_it,
    )
    questions = tuple(
        VoiQuestion(
            unknown_id=resolution.unknown_id,
            question=resolution.question or "Which missing detail would change how this runs?",
            voi_score=resolution.voi_score,
        )
        for resolution in profile.resolutions
        if resolution.resolution is Resolution.question
    )

    per_run = sum(node.cost_units for node in candidate.nodes)
    total = frame.budget_cap_units if frame.budget_cap_units is not None else per_run * max(
        frame.projected_runs or 1, 1
    )
    envelope = AuthorityEnvelope(
        envelope_id="env.{0}".format(objective.replace(".", "_")),
        objective_id=objective,
        principal_id=principal,
        granted=granted,
        lock_list=lock_list,
        questions=questions,
        budget_total_units=max(total, per_run),
        budget_per_run_units=per_run,
        expires_at=expires_at,
    )
    return CompileResult(
        envelope=envelope,
        requests=tuple(traced_requests),
        excluded=tuple(excluded),
        proceed_allowed_without_answers=profile.proceed_allowed_without_answers,
    )


def shrink_proposal(envelope: AuthorityEnvelope, used_capability_ids: set[str]) -> ShrinkProposal:
    """Usage-based shrink: trust goes up, scope goes down.

    The next envelope proposal for a similar objective keeps only what this
    run actually used; everything granted-but-unused is logged and dropped.
    """
    granted_ids = [grant.capability_id for grant in envelope.granted]
    kept = tuple(value for value in granted_ids if value in used_capability_ids)
    dropped = tuple(value for value in granted_ids if value not in used_capability_ids)
    return ShrinkProposal(kept=kept, dropped=dropped)


# --------------------------------------------------------------------- steps


def _select_candidate(frame: ObjectiveFrameInput, candidate_id: Optional[str]) -> WorkflowCandidate:
    if candidate_id is None:
        return frame.candidates[0]
    for candidate in frame.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise ValueError("candidate_not_found")


def _resolve_requests(
    candidate: WorkflowCandidate,
    capabilities: CapabilityStore,
) -> tuple[list[CapabilityRequest], list[ExcludedCapability]]:
    requests: list[CapabilityRequest] = []
    excluded: list[ExcludedCapability] = []
    for node in candidate.nodes:
        if node.kind is not NodeKind.capability or node.capability_ref is None:
            continue
        if capabilities.get(node.capability_ref) is None:
            excluded.append(
                ExcludedCapability(
                    capability_id=node.capability_ref,
                    node_id=node.node_id,
                    reason="capability_not_registered",
                )
            )
            continue
        args_shape: dict[str, str] = {}
        if node.path_scope is not None:
            args_shape["path"] = node.path_scope
        if node.network_host is not None:
            args_shape["network_host"] = node.network_host
        if node.credential_scope is not None:
            args_shape["credential_scope"] = node.credential_scope
        requests.append(
            CapabilityRequest(
                capability_id=node.capability_ref,
                derived_from=node.node_id,
                args_shape=args_shape,
            )
        )
    return requests, excluded


def _dependency_closure(candidate: WorkflowCandidate, frame: ObjectiveFrameInput) -> frozenset[str]:
    """Node ids that trace to a frame clause, directly or as a dependency.

    Anchors are nodes producing a required criterion (or any criterion when
    the frame names none). The closure walks edges backwards: a node is kept
    only if some anchor is reachable from it. Everything else is a freerider.
    """
    required = set(frame.required_criteria)
    anchors: set[str] = set()
    for node in candidate.nodes:
        produced = set(node.produces_criteria) | set(node.verifies_criteria)
        if required:
            if produced & required:
                anchors.add(node.node_id)
        elif produced:
            anchors.add(node.node_id)

    downstream: dict[str, set[str]] = {}
    for edge in candidate.edges:
        downstream.setdefault(edge.src, set()).add(edge.dst)

    traced: set[str] = set()

    def reaches_anchor(node_id: str, visiting: set[str]) -> bool:
        if node_id in anchors or node_id in traced:
            return True
        if node_id in visiting:
            return False
        visiting.add(node_id)
        return any(
            reaches_anchor(successor, visiting)
            for successor in downstream.get(node_id, set())
        )

    for node in candidate.nodes:
        if reaches_anchor(node.node_id, set()):
            traced.add(node.node_id)
    return frozenset(traced)


def _grant_for(request: CapabilityRequest, record: Optional[CapabilityRecord]) -> GrantedCapability:
    assert record is not None  # unresolved requests were excluded in step 2
    path = request.args_shape.get("path")
    host = request.args_shape.get("network_host")
    credential = request.args_shape.get("credential_scope")
    return GrantedCapability(
        capability_id=request.capability_id,
        tier=_tier_for(record, path_scoped=path is not None),
        provenance=request.derived_from,
        path_scopes=(path,) if path is not None else (),
        network_hosts=(host,) if host is not None else (),
        credential_scopes=(credential,) if credential is not None else (),
        taint_escalates=record.side_effect in _DANGEROUS_SIDE_EFFECTS,
    )


def _tier_for(record: CapabilityRecord, *, path_scoped: bool) -> GrantTier:
    """Step 4: read=auto · scoped local write=auto · normal write=ask_first
    (licensable) · public or irreversible=always_ask."""
    if record.reversibility is Reversibility.irreversible:
        return GrantTier.always_ask
    if record.side_effect is SideEffectClass.none:
        return GrantTier.auto
    if record.side_effect is SideEffectClass.local_write:
        return GrantTier.auto if path_scoped else GrantTier.ask_first
    if record.side_effect is SideEffectClass.account_write:
        return GrantTier.ask_first
    return GrantTier.always_ask


def _lock_list(
    granted: tuple[GrantedCapability, ...],
    capabilities: CapabilityStore,
) -> tuple[LockedCapability, ...]:
    granted_ids = {grant.capability_id for grant in granted}
    locks: dict[str, LockedCapability] = {}
    for grant in granted:
        record = capabilities.get(grant.capability_id)
        if record is None:
            continue
        for sibling in capabilities.siblings_by_verb(record.verb_class):
            if sibling.capability_id in granted_ids:
                continue
            dangerous = (
                sibling.side_effect in _DANGEROUS_SIDE_EFFECTS
                or sibling.reversibility is Reversibility.irreversible
            )
            if dangerous:
                locks[sibling.capability_id] = LockedCapability(
                    capability_id=sibling.capability_id,
                    reason="adjacent_dangerous_not_derived_from_objective",
                )
    return tuple(locks.values())
