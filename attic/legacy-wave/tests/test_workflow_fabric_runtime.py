from __future__ import annotations

import pytest

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.workflow_fabric_runtime import (
    NodeKind,
    WorkflowCandidate,
    WorkflowEdge,
    WorkflowNode,
    choose_workflow,
    verify_candidate,
)


def _n(node_id: str, kind: NodeKind = NodeKind.llm_generic, **overrides: object) -> WorkflowNode:
    base: dict[str, object] = {"node_id": node_id, "kind": kind}
    base.update(overrides)
    return WorkflowNode(**base)  # type: ignore[arg-type]


def _publish_node(node_id: str) -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        kind=NodeKind.capability,
        capability_ref="mcp.blog.publish",
        side_effect=SideEffectClass.public_write,
    )


# --- Approval dominance: the crown jewel ------------------------------------


def test_publish_without_gate_is_rejected() -> None:
    # research -> draft -> publish (no approval gate anywhere)
    candidate = WorkflowCandidate(
        candidate_id="ungated",
        nodes=(_n("research"), _n("draft"), _publish_node("publish")),
        edges=(WorkflowEdge(src="research", dst="draft"), WorkflowEdge(src="draft", dst="publish")),
    )
    verdict = verify_candidate(candidate)
    assert verdict.ok is False
    assert any(f.rule == "approval_dominance" and f.node_id == "publish" for f in verdict.findings)


def test_publish_behind_gate_passes() -> None:
    # research -> draft -> approve -> publish
    candidate = WorkflowCandidate(
        candidate_id="gated",
        nodes=(
            _n("research"),
            _n("draft"),
            _n("approve", NodeKind.approval_gate),
            _publish_node("publish"),
        ),
        edges=(
            WorkflowEdge(src="research", dst="draft"),
            WorkflowEdge(src="draft", dst="approve"),
            WorkflowEdge(src="approve", dst="publish"),
        ),
    )
    verdict = verify_candidate(candidate)
    assert verdict.ok is True


def test_gate_must_dominate_every_path() -> None:
    # A side path reaches publish without crossing the gate -> still rejected.
    #   start -> gate -> publish
    #   start --------> publish   (bypass)
    candidate = WorkflowCandidate(
        candidate_id="bypass",
        nodes=(_n("start"), _n("gate", NodeKind.approval_gate), _publish_node("publish")),
        edges=(
            WorkflowEdge(src="start", dst="gate"),
            WorkflowEdge(src="gate", dst="publish"),
            WorkflowEdge(src="start", dst="publish"),
        ),
    )
    verdict = verify_candidate(candidate)
    assert verdict.ok is False
    assert any(f.rule == "approval_dominance" for f in verdict.findings)


def test_local_write_also_needs_a_gate() -> None:
    candidate = WorkflowCandidate(
        candidate_id="localwrite",
        nodes=(
            _n("plan"),
            WorkflowNode(
                node_id="delete",
                kind=NodeKind.capability,
                capability_ref="builtin.fs.delete",
                side_effect=SideEffectClass.local_write,
            ),
        ),
        edges=(WorkflowEdge(src="plan", dst="delete"),),
    )
    assert verify_candidate(candidate).ok is False


# --- Coverage ----------------------------------------------------------------


def test_uncovered_criterion_fails() -> None:
    candidate = WorkflowCandidate(
        candidate_id="nocover",
        nodes=(_n("draft", produces_criteria=("post_written",)),),
    )
    verdict = verify_candidate(candidate, required_criteria=("post_written",))
    # Produced but never verified.
    assert verdict.ok is False
    assert any(f.detail == "unverified:post_written" for f in verdict.findings)


def test_produced_and_verified_criterion_passes() -> None:
    candidate = WorkflowCandidate(
        candidate_id="covered",
        nodes=(
            _n("draft", produces_criteria=("post_written",)),
            _n("check", NodeKind.verification, verifies_criteria=("post_written",)),
        ),
        edges=(WorkflowEdge(src="draft", dst="check"),),
    )
    verdict = verify_candidate(candidate, required_criteria=("post_written",))
    assert verdict.ok is True
    assert verdict.covered_criteria == ("post_written",)


# --- Budget & cycles ---------------------------------------------------------


def test_budget_overrun_fails() -> None:
    candidate = WorkflowCandidate(
        candidate_id="pricey",
        nodes=(_n("a", cost_units=10), _n("b", cost_units=10)),
        edges=(WorkflowEdge(src="a", dst="b"),),
    )
    assert verify_candidate(candidate, budget_cap_units=15).ok is False
    assert verify_candidate(candidate, budget_cap_units=25).ok is True


def test_cycle_is_detected() -> None:
    candidate = WorkflowCandidate(
        candidate_id="loop",
        nodes=(_n("a"), _n("b")),
        edges=(WorkflowEdge(src="a", dst="b"), WorkflowEdge(src="b", dst="a")),
    )
    verdict = verify_candidate(candidate)
    assert verdict.ok is False
    assert any(f.rule == "acyclic" for f in verdict.findings)


# --- Gaps are surfaced, not rejected ----------------------------------------


def test_gap_node_does_not_fail_but_is_flagged() -> None:
    candidate = WorkflowCandidate(
        candidate_id="withgap",
        nodes=(
            _n("research"),
            WorkflowNode(node_id="publish", kind=NodeKind.gap, missing_capability="mcp.tistory.publish"),
        ),
        edges=(WorkflowEdge(src="research", dst="publish"),),
    )
    verdict = verify_candidate(candidate)
    assert verdict.ok is True
    assert verdict.has_gaps is True


# --- Selection + decision record --------------------------------------------


def test_choose_prefers_clean_over_gapped_and_records_rejections() -> None:
    gated = WorkflowCandidate(
        candidate_id="clean",
        nodes=(_n("draft", produces_criteria=("c",)),
               _n("verify", NodeKind.verification, verifies_criteria=("c",))),
        edges=(WorkflowEdge(src="draft", dst="verify"),),
    )
    gapped = WorkflowCandidate(
        candidate_id="gapped",
        nodes=(_n("draft", produces_criteria=("c",)),
               _n("verify", NodeKind.verification, verifies_criteria=("c",)),
               WorkflowNode(node_id="extra", kind=NodeKind.gap, missing_capability="mcp.x")),
        edges=(WorkflowEdge(src="draft", dst="verify"),),
    )
    ungated = WorkflowCandidate(
        candidate_id="ungated",
        nodes=(_publish_node("publish"),),
    )
    decision = choose_workflow((gapped, ungated, gated), required_criteria=("c",))
    assert decision.chosen_candidate_id == "clean"
    assert "ungated" in decision.rejected
    assert decision.reason == "chosen_clean"


def test_choose_returns_none_when_all_fail() -> None:
    ungated = WorkflowCandidate(candidate_id="ungated", nodes=(_publish_node("publish"),))
    decision = choose_workflow((ungated,))
    assert decision.chosen_candidate_id is None
    assert decision.reason == "all_candidates_failed_verification"


def test_only_capability_nodes_may_carry_side_effects() -> None:
    with pytest.raises(ValueError):
        WorkflowNode(node_id="bad", kind=NodeKind.llm_generic, side_effect=SideEffectClass.public_write)


def test_command_node_cannot_underdeclare_side_effect() -> None:
    # An LLM labeling `rm -rf` as side_effect=none must be caught by the fabric.
    candidate = WorkflowCandidate(
        candidate_id="sneaky",
        nodes=(WorkflowNode(node_id="wipe", kind=NodeKind.llm_generic, command="rm -rf /data"),),
    )
    verdict = verify_candidate(candidate)
    assert verdict.ok is False
    assert any(f.rule == "command_risk" and f.node_id == "wipe" for f in verdict.findings)


def test_command_node_with_honest_side_effect_and_gate_passes() -> None:
    # A destructive command, honestly declared account_write and gated, passes.
    candidate = WorkflowCandidate(
        candidate_id="honest",
        nodes=(
            _n("plan"),
            _n("gate", NodeKind.approval_gate),
            WorkflowNode(node_id="wipe", kind=NodeKind.capability, capability_ref="sandbox.run",
                         side_effect=SideEffectClass.account_write, command="rm -rf /data"),
        ),
        edges=(WorkflowEdge(src="plan", dst="gate"), WorkflowEdge(src="gate", dst="wipe")),
    )
    assert verify_candidate(candidate).ok is True


def test_read_only_command_node_is_fine() -> None:
    candidate = WorkflowCandidate(
        candidate_id="readonly",
        nodes=(WorkflowNode(node_id="look", kind=NodeKind.llm_generic, command="cat README.md"),),
    )
    assert verify_candidate(candidate).ok is True
