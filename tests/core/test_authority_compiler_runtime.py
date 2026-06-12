from __future__ import annotations

import pytest

from zeus_agent.authority_compiler_runtime import (
    EnvelopeStore,
    GrantTier,
    compile_envelope,
    derive_child_authority,
    shrink_proposal,
)
from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityStore,
    CapabilityTrust,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)
from zeus_agent.objective_card_runtime import ObjectiveFrameInput
from zeus_agent.objective_risk_runtime import (
    BlastRadius,
    Irreversibility,
    RiskClass,
    SafeDefault,
    Triage,
    Unknown,
)
from zeus_agent.trust_loop_runtime import Reversibility
from zeus_agent.workflow_fabric_runtime import (
    NodeKind,
    WorkflowCandidate,
    WorkflowEdge,
    WorkflowNode,
)


def _record(
    capability_id: str,
    *,
    verb: VerbClass,
    side_effect: SideEffectClass = SideEffectClass.none,
    reversibility: Reversibility = Reversibility.reversible,
) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=verb,
        title=capability_id,
        input_summary="input",
        output_summary="output",
        side_effect=side_effect,
        reversibility=reversibility,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=CapabilityStatus.active,
    )


def _store() -> CapabilityStore:
    return CapabilityStore(
        [
            _record("fs.read", verb=VerbClass.fetch),
            _record("fs.write", verb=VerbClass.store, side_effect=SideEffectClass.local_write),
            _record(
                "mail.send",
                verb=VerbClass.notify,
                side_effect=SideEffectClass.account_write,
                reversibility=Reversibility.compensable,
            ),
            _record(
                "sms.broadcast",
                verb=VerbClass.notify,
                side_effect=SideEffectClass.public_write,
                reversibility=Reversibility.irreversible,
            ),
            _record(
                "db.drop",
                verb=VerbClass.store,
                side_effect=SideEffectClass.account_write,
                reversibility=Reversibility.irreversible,
            ),
        ]
    )


def _node(
    node_id: str,
    capability: str | None,
    *,
    produces: tuple[str, ...] = (),
    side_effect: SideEffectClass = SideEffectClass.none,
    path_scope: str | None = None,
    cost: int = 1,
) -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        kind=NodeKind.capability if capability is not None else NodeKind.llm_generic,
        capability_ref=capability,
        side_effect=side_effect if capability is not None else SideEffectClass.none,
        produces_criteria=produces,
        path_scope=path_scope,
        cost_units=cost,
    )


def _frame(candidate: WorkflowCandidate, **overrides) -> ObjectiveFrameInput:
    fields = {
        "normalized_objective": "Summarize inbox and notify the team",
        "triage": Triage.oneshot,
        "candidates": (candidate,),
        "required_criteria": ("summary-delivered",),
    }
    fields.update(overrides)
    return ObjectiveFrameInput(**fields)


def _basic_candidate() -> WorkflowCandidate:
    return WorkflowCandidate(
        candidate_id="cand.1",
        nodes=(
            _node("n.read", "fs.read"),
            _node(
                "n.send",
                "mail.send",
                produces=("summary-delivered",),
                side_effect=SideEffectClass.account_write,
            ),
        ),
        edges=(WorkflowEdge(src="n.read", dst="n.send"),),
    )


def test_compile_grants_only_traced_capabilities() -> None:
    result = compile_envelope(
        frame=_frame(_basic_candidate()),
        objective_id="obj.compile.1",
        principal_id="operator.local",
        capabilities=_store(),
    )
    granted_ids = {grant.capability_id for grant in result.envelope.granted}
    assert granted_ids == {"fs.read", "mail.send"}


def test_freerider_node_is_excluded() -> None:
    candidate = WorkflowCandidate(
        candidate_id="cand.2",
        nodes=(
            _node("n.read", "fs.read"),
            _node(
                "n.send",
                "mail.send",
                produces=("summary-delivered",),
                side_effect=SideEffectClass.account_write,
            ),
            # "하는 김에" node: writes locally, feeds nothing required.
            _node(
                "n.extra",
                "fs.write",
                side_effect=SideEffectClass.local_write,
                path_scope="/tmp/extra",
            ),
        ),
        edges=(WorkflowEdge(src="n.read", dst="n.send"),),
    )
    result = compile_envelope(
        frame=_frame(candidate),
        objective_id="obj.compile.2",
        principal_id="operator.local",
        capabilities=_store(),
    )
    granted_ids = {grant.capability_id for grant in result.envelope.granted}
    assert "fs.write" not in granted_ids
    assert any(
        item.capability_id == "fs.write" and item.reason == "untraced_to_frame_clause"
        for item in result.excluded
    )


def test_dependency_of_anchor_is_traced() -> None:
    result = compile_envelope(
        frame=_frame(_basic_candidate()),
        objective_id="obj.compile.3",
        principal_id="operator.local",
        capabilities=_store(),
    )
    read_grant = result.envelope.grant_for("fs.read")
    assert read_grant is not None
    assert read_grant.provenance == "n.read"


def test_tier_partition_read_auto_write_ask_irreversible_always() -> None:
    candidate = WorkflowCandidate(
        candidate_id="cand.3",
        nodes=(
            _node("n.read", "fs.read", produces=("c1",)),
            _node(
                "n.write",
                "fs.write",
                produces=("c2",),
                side_effect=SideEffectClass.local_write,
                path_scope="/work",
            ),
            _node(
                "n.send",
                "mail.send",
                produces=("c3",),
                side_effect=SideEffectClass.account_write,
            ),
            _node(
                "n.drop",
                "db.drop",
                produces=("c4",),
                side_effect=SideEffectClass.account_write,
            ),
        ),
    )
    result = compile_envelope(
        frame=_frame(candidate, required_criteria=("c1", "c2", "c3", "c4")),
        objective_id="obj.compile.4",
        principal_id="operator.local",
        capabilities=_store(),
    )
    tiers = {grant.capability_id: grant.tier for grant in result.envelope.granted}
    assert tiers["fs.read"] is GrantTier.auto
    assert tiers["fs.write"] is GrantTier.auto  # path-scoped local write
    assert tiers["mail.send"] is GrantTier.ask_first
    assert tiers["db.drop"] is GrantTier.always_ask  # irreversible


def test_lock_list_covers_dangerous_unrequested_siblings() -> None:
    result = compile_envelope(
        frame=_frame(_basic_candidate()),
        objective_id="obj.compile.5",
        principal_id="operator.local",
        capabilities=_store(),
    )
    locked_ids = {lock.capability_id for lock in result.envelope.lock_list}
    # sms.broadcast shares VerbClass.notify with mail.send, is public+irreversible,
    # and was never derived from the objective → explicit lock.
    assert "sms.broadcast" in locked_ids
    assert result.envelope.locked("sms.broadcast") is not None


def test_taint_overlay_marks_external_sinks() -> None:
    result = compile_envelope(
        frame=_frame(_basic_candidate()),
        objective_id="obj.compile.6",
        principal_id="operator.local",
        capabilities=_store(),
    )
    send = result.envelope.grant_for("mail.send")
    read = result.envelope.grant_for("fs.read")
    assert send is not None and send.taint_escalates
    assert read is not None and not read.taint_escalates


def test_voi_questions_only_above_threshold() -> None:
    high_stakes = Unknown(
        unknown_id="u.recipient",
        description="Who receives the broadcast",
        risk_class=RiskClass.external,
        irreversibility=Irreversibility.high,
        blast_radius=BlastRadius.public,
        cost_bucket=3,
        failure_probability=0.6,
        question_text="Who exactly should receive this?",
    )
    trivial = Unknown(
        unknown_id="u.filename",
        description="Output file name",
        risk_class=RiskClass.quality,
        irreversibility=Irreversibility.low,
        blast_radius=BlastRadius.local,
        cost_bucket=1,
        failure_probability=0.2,
        safe_default=SafeDefault(value="summary.md", rationale="conventional name"),
    )
    result = compile_envelope(
        frame=_frame(_basic_candidate(), unknowns=(high_stakes, trivial)),
        objective_id="obj.compile.7",
        principal_id="operator.local",
        capabilities=_store(),
    )
    question_ids = {question.unknown_id for question in result.envelope.questions}
    assert "u.recipient" in question_ids
    assert "u.filename" not in question_ids


def test_budget_from_frame_cap_and_node_costs() -> None:
    result = compile_envelope(
        frame=_frame(_basic_candidate(), budget_cap_units=50),
        objective_id="obj.compile.8",
        principal_id="operator.local",
        capabilities=_store(),
    )
    assert result.envelope.budget_total_units == 50
    assert result.envelope.budget_per_run_units == 2


def test_unregistered_capability_is_excluded_not_granted() -> None:
    candidate = WorkflowCandidate(
        candidate_id="cand.4",
        nodes=(
            _node("n.read", "fs.read", produces=("summary-delivered",)),
            _node("n.ghost", "ghost.tool", produces=("summary-delivered",)),
        ),
    )
    result = compile_envelope(
        frame=_frame(candidate),
        objective_id="obj.compile.9",
        principal_id="operator.local",
        capabilities=_store(),
    )
    assert {grant.capability_id for grant in result.envelope.granted} == {"fs.read"}
    assert any(item.reason == "capability_not_registered" for item in result.excluded)


def test_shrink_proposal_drops_unused_grants() -> None:
    result = compile_envelope(
        frame=_frame(_basic_candidate()),
        objective_id="obj.compile.10",
        principal_id="operator.local",
        capabilities=_store(),
    )
    proposal = shrink_proposal(result.envelope, used_capability_ids={"fs.read"})
    assert proposal.kept == ("fs.read",)
    assert proposal.dropped == ("mail.send",)


def test_envelope_store_burn_after_use() -> None:
    store = EnvelopeStore()
    result = compile_envelope(
        frame=_frame(_basic_candidate()),
        objective_id="obj.compile.11",
        principal_id="operator.local",
        capabilities=_store(),
    )
    store.put(result.envelope)
    store.burn("obj.compile.11", "mail.send")
    refreshed = store.active_for("obj.compile.11")
    assert refreshed is not None
    assert refreshed.grant_for("mail.send") is None  # burned grants stop matching
    assert refreshed.grant_for("fs.read") is not None


def test_child_attenuation_raises_outside_envelope() -> None:
    result = compile_envelope(
        frame=_frame(_basic_candidate()),
        objective_id="obj.compile.12",
        principal_id="operator.local",
        capabilities=_store(),
    )
    child = derive_child_authority(
        result.envelope,
        run_id="run.child",
        child_principal_id="agent.child",
        requested_capabilities=("fs.read",),
    )
    assert child.allows("fs.read").decision == "allowed"
    with pytest.raises(ValueError):
        derive_child_authority(
            result.envelope,
            run_id="run.child",
            child_principal_id="agent.child",
            requested_capabilities=("sms.broadcast",),
        )
