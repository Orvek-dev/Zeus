from __future__ import annotations

from pathlib import Path
from typing import Callable, Final, Optional, Protocol

from pydantic import JsonValue

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.execution_integrity_runtime import assert_claim, claim_from_decision_receipt
from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    GovernedExecutionDispatcher,
    Reversibility,
    SQLiteEvidenceLedger,
    TrustLedger,
    TrustLoopAction,
)
from zeus_agent.workflow_fabric_runtime import NodeKind, WorkflowCandidate, WorkflowNode

from .models import NodeState, RunState, RunStatus
from .state_store import WorkflowExecutionStateStore

_CRITERION_ID: Final = "REQ-ZEUS-EXEC-001:S1"
_EVIDENCE_TARGET: Final = "mneme.workflow_execution"

# Side effect → (risk, reversibility) for the trust-loop action. Drives whether
# a node needs an approval before the dispatcher will run it.
_RISK_BY_EFFECT: Final[dict[SideEffectClass, tuple[ActionRisk, Reversibility]]] = {
    SideEffectClass.none: (ActionRisk.low, Reversibility.reversible),
    SideEffectClass.local_write: (ActionRisk.medium, Reversibility.compensable),
    SideEffectClass.account_write: (ActionRisk.high, Reversibility.irreversible),
    SideEffectClass.public_write: (ActionRisk.high, Reversibility.irreversible),
}

# A verifier runs a real check for a verification node. The default passes when
# the node declares criteria (the seam where parsing test output / artifacts /
# the self-critic plug in for M4). Returning False fails the node.
Verifier = Callable[[WorkflowNode, RunState], bool]
CapabilityApprovals = dict[str, tuple[ApprovalReceipt, ApprovalEnvelope]]


class _KillSwitchLike(Protocol):
    def is_blocked(self, *, run_id: Optional[str] = ..., capability_id: Optional[str] = ...) -> Optional[str]:
        ...


def _default_verifier(node: WorkflowNode, run: RunState) -> bool:
    """A REAL verification (not a stub): a verification node passes only if every
    criterion it verifies was actually produced by a succeeded upstream node that
    left an evidence receipt, and any declared artifacts exist on disk.

    This fails a mis-wired workflow (verifying something never produced, or whose
    producer failed) — so "completion by evidence" rests on the run's actual
    evidence, not on the node merely declaring it verifies something.
    """
    for artifact in node.expected_artifacts:
        if not Path(artifact).exists():
            return False
    if not node.verifies_criteria:
        return True
    candidate = WorkflowCandidate.model_validate_json(run.candidate_json)
    producers: dict[str, list[str]] = {}
    for producer in candidate.nodes:
        for criterion in producer.produces_criteria:
            producers.setdefault(criterion, []).append(producer.node_id)
    for criterion in node.verifies_criteria:
        candidates_for = producers.get(criterion, [])
        if not candidates_for:
            return False  # verifying a criterion nothing produces
        produced = any(
            run.node_states.get(node_id) is NodeState.succeeded and node_id in run.node_receipts
            for node_id in candidates_for
        )
        if not produced:
            return False  # the producer did not succeed / left no evidence
    return True


class WorkflowExecutionRuntime:
    """Walks a verified workflow DAG, dispatching every side-effecting node
    through the single ``GovernedExecutionDispatcher`` chokepoint, suspending at
    approval gates, and judging completion by evidence alone.

    The executor orchestrates; the dispatcher authorizes. A capability node is
    NEVER run directly — only via ``dispatcher.dispatch`` — so no side effect can
    occur without broker evidence (enforced inline by ``assert_claim``).
    """

    def __init__(
        self,
        *,
        dispatcher: GovernedExecutionDispatcher,
        ledger: SQLiteEvidenceLedger,
        state_store: WorkflowExecutionStateStore,
        trust_ledger: Optional[TrustLedger] = None,
        verifier: Optional[Verifier] = None,
        replanner: Optional[Callable[[RunState, str], None]] = None,
        kill_switch: Optional["_KillSwitchLike"] = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._ledger = ledger
        self._store = state_store
        self._trust = trust_ledger if trust_ledger is not None else TrustLedger()
        self._verify = verifier if verifier is not None else _default_verifier
        self._replan = replanner
        self._kill = kill_switch

    def start(
        self,
        candidate: WorkflowCandidate,
        *,
        lease: RuntimeLease,
        objective_id: str,
        required_criteria: tuple[str, ...] = (),
    ) -> RunState:
        run = RunState(
            run_id=lease.run_id,
            objective_id=objective_id,
            candidate_id=candidate.candidate_id,
            candidate_json=candidate.model_dump_json(),
            node_states={node.node_id: NodeState.pending for node in candidate.nodes},
            required_criteria=required_criteria,
            budget_limit=lease.budget_limit,
        )
        self._store.save(run)
        return self._advance(run, lease, {})

    def resume(
        self,
        run_id: str,
        *,
        lease: RuntimeLease,
        approved_gates: tuple[str, ...] = (),
        capability_approvals: Optional[CapabilityApprovals] = None,
    ) -> RunState:
        run = self._store.load(run_id)
        if run is None:
            raise ValueError("unknown_run:{0}".format(run_id))
        # Idempotent: a finished run is returned untouched, never re-executed.
        if run.status in {RunStatus.completed, RunStatus.failed}:
            return run
        # ONLY the gates the operator explicitly named are cleared. Resuming with
        # no approval clears nothing — a gate cannot be passed without an approval.
        candidate = WorkflowCandidate.model_validate_json(run.candidate_json)
        nodes = {node.node_id: node for node in candidate.nodes}
        preds = _predecessors(candidate)
        approved = set(approved_gates)
        cleared = False
        for node_id, state in list(run.node_states.items()):
            if state is NodeState.waiting_approval and node_id in approved:
                run.node_states[node_id] = NodeState.succeeded
                self._append_node_event(run, nodes[node_id], preds, status="approval_granted")
                cleared = True
        if not cleared:
            # Nothing approved → stay suspended; do not advance past the gate.
            self._store.save(run)
            return run
        return self._advance(run, lease, capability_approvals or {})

    def _advance(self, run: RunState, lease: RuntimeLease, approvals: CapabilityApprovals) -> RunState:
        # We are actively advancing: clear any prior suspended status so a clean
        # finish can settle to completed (a re-suspend below resets it again).
        run.status = RunStatus.running
        candidate = WorkflowCandidate.model_validate_json(run.candidate_json)
        nodes = {node.node_id: node for node in candidate.nodes}
        order = _topo_order(candidate)
        preds = _predecessors(candidate)

        while True:
            ready = self._next_ready(order, nodes, run, preds)
            if ready is None:
                break
            if self._process(run, ready, preds, lease, approvals):
                self._store.save(run)
                return run

        self._finalize(run, nodes)
        self._store.save(run)
        return run

    def _next_ready(
        self,
        order: list[str],
        nodes: dict[str, WorkflowNode],
        run: RunState,
        preds: dict[str, set[str]],
    ) -> Optional[WorkflowNode]:
        for node_id in order:
            if run.node_states.get(node_id) is not NodeState.pending:
                continue
            if all(
                run.node_states.get(pred) in {NodeState.succeeded, NodeState.skipped}
                for pred in preds[node_id]
            ):
                return nodes[node_id]
        return None

    def _process(
        self,
        run: RunState,
        node: WorkflowNode,
        preds: dict[str, set[str]],
        lease: RuntimeLease,
        approvals: CapabilityApprovals,
    ) -> bool:
        """Process one ready node. Returns True if the run must stop now
        (suspended, blocked, or failed)."""
        # Kill switch is consulted before every node: an engaged switch halts the
        # run at the next step rather than letting it run to completion.
        if self._kill is not None:
            revoked = self._kill.is_blocked(run_id=run.run_id, capability_id=node.capability_ref)
            if revoked is not None:
                run.status = RunStatus.blocked
                run.blocked_reason = "revoked:{0}".format(revoked)
                self._append_node_event(run, node, preds, status="revoked", reason=revoked)
                return True

        if node.kind is NodeKind.gap:
            run.status = RunStatus.blocked
            run.blocked_reason = "needs_connection:{0}".format(node.missing_capability)
            return True

        if run.budget_limit > 0 and run.budget_spent_units + node.cost_units > run.budget_limit:
            run.status = RunStatus.blocked
            run.blocked_reason = "over_budget"
            return True

        if node.kind is NodeKind.approval_gate:
            run.node_states[node.node_id] = NodeState.waiting_approval
            run.status = RunStatus.waiting_approval
            self._append_node_event(run, node, preds, status="waiting_approval")
            return True

        run.budget_spent_units += node.cost_units

        if node.kind is NodeKind.capability:
            return self._run_capability(run, node, preds, lease, approvals)

        if node.kind is NodeKind.verification:
            passed = self._verify(node, run)
            if not passed:
                return self._fail(run, node, preds, reason="verification_failed")
            run.node_states[node.node_id] = NodeState.succeeded
            self._append_node_event(run, node, preds, status="succeeded")
            return False

        # llm_generic and any other side-effect-free in-runtime node.
        run.node_states[node.node_id] = NodeState.succeeded
        self._append_node_event(run, node, preds, status="succeeded")
        return False

    def _run_capability(
        self,
        run: RunState,
        node: WorkflowNode,
        preds: dict[str, set[str]],
        lease: RuntimeLease,
        approvals: CapabilityApprovals,
    ) -> bool:
        action = self._action(run, node)
        auth = approvals.get(node.capability_ref or "")
        receipt = self._dispatcher.dispatch(
            action,
            lease=lease,
            approval=auth[0] if auth else None,
            approval_envelope=auth[1] if auth else None,
        )
        # Inline chokepoint enforcement: an executed handler must carry evidence.
        assert_claim(claim_from_decision_receipt(receipt, surface="node:{0}".format(node.node_id)))

        if not receipt.handler_executed:
            self._trust.record_failure(action)
            return self._fail(
                run, node, preds, reason=receipt.blocked_reason or "capability_blocked",
                dispatch_record_id=receipt.evidence_record_id,
            )
        # The handler RAN, but a tool/provider can run and still fail (e.g. a
        # provider transport error). An executed-with-error result is a workflow
        # failure AND a trust failure — not a success.
        tool_error = _result_error(receipt.result)
        if tool_error is not None:
            self._trust.record_failure(action)
            return self._fail(
                run, node, preds, reason="tool_error:{0}".format(tool_error),
                dispatch_record_id=receipt.evidence_record_id,
            )
        self._trust.record_success(action)
        run.node_states[node.node_id] = NodeState.succeeded
        self._append_node_event(
            run, node, preds, status="succeeded", dispatch_record_id=receipt.evidence_record_id
        )
        return False

    def _fail(
        self,
        run: RunState,
        node: WorkflowNode,
        preds: dict[str, set[str]],
        *,
        reason: str,
        dispatch_record_id: Optional[str] = None,
    ) -> bool:
        run.node_states[node.node_id] = NodeState.failed
        run.status = RunStatus.failed
        run.blocked_reason = reason
        self._append_node_event(
            run, node, preds, status="failed", dispatch_record_id=dispatch_record_id, reason=reason
        )
        self._rollback_side_effects(run, exclude=node.node_id)
        if self._replan is not None:
            self._replan(run, reason)
        return True

    def _rollback_side_effects(self, run: RunState, *, exclude: str) -> None:
        candidate = WorkflowCandidate.model_validate_json(run.candidate_json)
        for node in candidate.nodes:
            if node.node_id == exclude:
                continue
            if run.node_states.get(node.node_id) is not NodeState.succeeded:
                continue
            if node.side_effect is SideEffectClass.none:
                continue
            event = self._ledger.append(
                kind="rollback",
                run_id=run.run_id,
                payload={
                    "node_id": node.node_id,
                    "compensates_record_id": run.node_receipts.get(node.node_id),
                    "reason": "run_failed_rollback",
                },
            )
            run.node_receipts["{0}:rollback".format(node.node_id)] = event.record_id
            run.node_states[node.node_id] = NodeState.rolled_back

    def _finalize(self, run: RunState, nodes: dict[str, WorkflowNode]) -> None:
        if run.status in {RunStatus.failed, RunStatus.blocked, RunStatus.waiting_approval}:
            return
        all_terminal = all(run.is_node_terminal(node_id) for node_id in nodes)
        if not all_terminal:
            run.status = RunStatus.blocked
            run.blocked_reason = "stuck_unreachable_nodes"
            return
        # Completion is judged by evidence: every required criterion must have a
        # succeeded verification node that verifies it.
        for criterion in run.required_criteria:
            verified = any(
                criterion in node.verifies_criteria
                and run.node_states.get(node.node_id) is NodeState.succeeded
                for node in nodes.values()
            )
            if not verified:
                run.status = RunStatus.blocked
                run.blocked_reason = "criterion_unverified:{0}".format(criterion)
                return
        run.status = RunStatus.completed

    def _action(self, run: RunState, node: WorkflowNode) -> TrustLoopAction:
        risk, reversibility = _RISK_BY_EFFECT[node.side_effect]
        return TrustLoopAction(
            action_id="{0}.{1}".format(run.run_id, node.node_id),
            run_id=run.run_id,
            goal_contract_id=run.objective_id,
            criterion_id=_CRITERION_ID,
            capability_id=node.capability_ref or "provider.fake.generate",
            payload={"node_id": node.node_id},
            risk=risk,
            reversibility=reversibility,
            budget=BudgetEnvelope(max_units=max(run.budget_limit, 1), requested_units=node.cost_units),
            evidence_target=_EVIDENCE_TARGET,
            credential_scope=node.credential_scope,
            network_host=node.network_host,
            live_network=node.live_network,
        )

    def _append_node_event(
        self,
        run: RunState,
        node: WorkflowNode,
        preds: dict[str, set[str]],
        *,
        status: str,
        dispatch_record_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        caused_by = [
            run.node_receipts[pred]
            for pred in preds[node.node_id]
            if pred in run.node_receipts
        ]
        payload: dict[str, object] = {
            "node_id": node.node_id,
            "kind": node.kind.value,
            "status": status,
            "caused_by": caused_by,
        }
        if dispatch_record_id is not None:
            payload["dispatch_record_id"] = dispatch_record_id
        if reason is not None:
            payload["reason"] = reason
        event = self._ledger.append(kind="workflow_node", run_id=run.run_id, payload=payload)
        run.node_receipts[node.node_id] = event.record_id


def _result_error(result: Optional[dict[str, JsonValue]]) -> Optional[str]:
    """Extract a tool/provider error from a handler result, if any."""
    if result is None:
        return None
    err = result.get("error")
    if isinstance(err, str) and err.strip() != "":
        return err
    if result.get("ok") is False:
        return "tool_failed"
    return None


def _predecessors(candidate: WorkflowCandidate) -> dict[str, set[str]]:
    preds: dict[str, set[str]] = {node.node_id: set() for node in candidate.nodes}
    for edge in candidate.edges:
        preds[edge.dst].add(edge.src)
    return preds


def _topo_order(candidate: WorkflowCandidate) -> list[str]:
    preds = _predecessors(candidate)
    succ: dict[str, set[str]] = {node.node_id: set() for node in candidate.nodes}
    for edge in candidate.edges:
        succ[edge.src].add(edge.dst)
    remaining = {node_id: set(parents) for node_id, parents in preds.items()}
    order: list[str] = []
    ready = sorted(node_id for node_id, parents in remaining.items() if not parents)
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for nxt in sorted(succ[node_id]):
            remaining[nxt].discard(node_id)
            if not remaining[nxt]:
                ready.append(nxt)
    for node_id in remaining:
        if node_id not in order:
            order.append(node_id)
    return order
