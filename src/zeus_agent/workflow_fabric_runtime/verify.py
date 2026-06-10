from __future__ import annotations

from typing import Final, Optional

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.command_risk_runtime import classify_command

from .models import (
    CandidateVerdict,
    NodeKind,
    VerificationFinding,
    WorkflowCandidate,
)

_SIDE_EFFECT_RANK: Final[dict[SideEffectClass, int]] = {
    SideEffectClass.none: 0,
    SideEffectClass.local_write: 1,
    SideEffectClass.account_write: 2,
    SideEffectClass.public_write: 3,
}


def verify_candidate(
    candidate: WorkflowCandidate,
    *,
    required_criteria: tuple[str, ...] = (),
    budget_cap_units: Optional[int] = None,
) -> CandidateVerdict:
    """Run every static gate. A candidate is ok only if all gates pass.

    Gaps (unfilled capabilities) do NOT fail a candidate — they are surfaced so
    the user can connect the missing tool or handle the step manually.
    """
    findings: list[VerificationFinding] = []

    cycle = _find_cycle(candidate)
    if cycle is not None:
        findings.append(VerificationFinding(rule="acyclic", detail="cycle_through:{0}".format(cycle)))

    # Approval-dominance: every side-effecting node must be dominated by an
    # approval gate. Skip when the graph has a cycle (dominators are undefined).
    if cycle is None:
        findings.extend(_approval_dominance_findings(candidate))

    # Command-risk: a node that runs a shell command cannot under-declare its
    # side effect. We re-classify the command and require the declared side
    # effect to be at least as severe — so an LLM cannot label `rm -rf` as
    # side_effect=none to slip past approval-dominance.
    for node in candidate.nodes:
        if node.command is None:
            continue
        classified = classify_command(node.command).side_effect
        if _SIDE_EFFECT_RANK[node.side_effect] < _SIDE_EFFECT_RANK[classified]:
            findings.append(
                VerificationFinding(
                    rule="command_risk",
                    detail="declared_{0}_below_classified_{1}".format(
                        node.side_effect.value, classified.value
                    ),
                    node_id=node.node_id,
                )
            )

    covered = _coverage(candidate, required_criteria)
    for criterion in required_criteria:
        produced = any(criterion in node.produces_criteria for node in candidate.nodes)
        verified = any(criterion in node.verifies_criteria for node in candidate.nodes)
        if not produced:
            findings.append(VerificationFinding(rule="coverage", detail="unproduced:{0}".format(criterion)))
        elif not verified:
            findings.append(VerificationFinding(rule="coverage", detail="unverified:{0}".format(criterion)))

    total_cost = sum(node.cost_units for node in candidate.nodes)
    if budget_cap_units is not None and total_cost > budget_cap_units:
        findings.append(
            VerificationFinding(
                rule="budget",
                detail="cost_{0}_over_cap_{1}".format(total_cost, budget_cap_units),
            )
        )

    has_gaps = any(node.kind is NodeKind.gap for node in candidate.nodes)
    blocking = tuple(f for f in findings if f.rule != "gap")
    return CandidateVerdict(
        candidate_id=candidate.candidate_id,
        ok=len(blocking) == 0,
        findings=tuple(findings),
        has_gaps=has_gaps,
        total_cost_units=total_cost,
        covered_criteria=covered,
    )


def _approval_dominance_findings(candidate: WorkflowCandidate) -> list[VerificationFinding]:
    dominators = _dominators(candidate)
    gates = {node.node_id for node in candidate.nodes if node.kind is NodeKind.approval_gate}
    findings: list[VerificationFinding] = []
    for node in candidate.nodes:
        if node.side_effect is SideEffectClass.none:
            continue
        dominating_gates = (dominators.get(node.node_id, set()) - {node.node_id}) & gates
        if not dominating_gates:
            findings.append(
                VerificationFinding(
                    rule="approval_dominance",
                    detail="side_effect_{0}_not_gated".format(node.side_effect.value),
                    node_id=node.node_id,
                )
            )
    return findings


def _dominators(candidate: WorkflowCandidate) -> dict[str, set[str]]:
    """Classic iterative dominator computation over a virtual super-source.

    A node A dominates node N if every path from an entry node to N passes
    through A. Entry nodes (no predecessors) are dominated only by the virtual
    source, modelled here as each entry dominating only itself.
    """
    node_ids = [node.node_id for node in candidate.nodes]
    preds: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for edge in candidate.edges:
        preds[edge.dst].add(edge.src)

    entries = [nid for nid in node_ids if not preds[nid]]
    all_ids = set(node_ids)
    dom: dict[str, set[str]] = {nid: set(all_ids) for nid in node_ids}
    for entry in entries:
        dom[entry] = {entry}

    order = _topo_order(candidate, preds)
    changed = True
    while changed:
        changed = False
        for nid in order:
            if nid in entries:
                continue
            if not preds[nid]:
                new_dom = {nid}
            else:
                new_dom = set(all_ids)
                for pred in preds[nid]:
                    new_dom &= dom[pred]
                new_dom |= {nid}
            if new_dom != dom[nid]:
                dom[nid] = new_dom
                changed = True
    return dom


def _topo_order(candidate: WorkflowCandidate, preds: dict[str, set[str]]) -> list[str]:
    remaining = {node.node_id: set(preds[node.node_id]) for node in candidate.nodes}
    succ: dict[str, set[str]] = {node.node_id: set() for node in candidate.nodes}
    for edge in candidate.edges:
        succ[edge.src].add(edge.dst)
    order: list[str] = []
    ready = [nid for nid, ps in remaining.items() if not ps]
    while ready:
        nid = ready.pop()
        order.append(nid)
        for nxt in succ[nid]:
            remaining[nxt].discard(nid)
            if not remaining[nxt]:
                ready.append(nxt)
    # Any nodes left are in a cycle; append them so callers still see them.
    for nid in remaining:
        if nid not in order:
            order.append(nid)
    return order


def _find_cycle(candidate: WorkflowCandidate) -> Optional[str]:
    succ: dict[str, set[str]] = {node.node_id: set() for node in candidate.nodes}
    for edge in candidate.edges:
        succ[edge.src].add(edge.dst)
    visited: set[str] = set()
    in_stack: set[str] = set()

    def walk(nid: str) -> Optional[str]:
        visited.add(nid)
        in_stack.add(nid)
        for nxt in succ[nid]:
            if nxt in in_stack:
                return nxt
            if nxt not in visited:
                found = walk(nxt)
                if found is not None:
                    return found
        in_stack.discard(nid)
        return None

    for node in candidate.nodes:
        if node.node_id not in visited:
            found = walk(node.node_id)
            if found is not None:
                return found
    return None


def _coverage(candidate: WorkflowCandidate, required: tuple[str, ...]) -> tuple[str, ...]:
    covered: list[str] = []
    for criterion in required:
        produced = any(criterion in node.produces_criteria for node in candidate.nodes)
        verified = any(criterion in node.verifies_criteria for node in candidate.nodes)
        if produced and verified:
            covered.append(criterion)
    return tuple(covered)
