from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    ApprovalEnvelope,
    BudgetEnvelope,
    GovernedExecutionDispatcher,
    Reversibility,
    SQLiteEvidenceLedger,
    SQLiteTrustStatStore,
    TrustLedger,
)
from zeus_agent.workflow_execution_runtime import (
    NodeState,
    RunStatus,
    WorkflowExecutionRuntime,
    WorkflowExecutionStateStore,
)
from zeus_agent.workflow_fabric_runtime import (
    NodeKind,
    WorkflowCandidate,
    WorkflowEdge,
    WorkflowNode,
)

_EVIDENCE_TARGET = "mneme.workflow_execution"


def _lease(run_id: str, objective_id: str, *, capability: str, budget: int = 100) -> RuntimeLease:
    now = datetime.now(timezone.utc)
    return RuntimeLease(
        lease_id="{0}.lease".format(run_id),
        objective_id=objective_id,
        principal_id="operator.local",
        run_id=run_id,
        allowed_capabilities=(capability,),
        credential_scopes=(),
        network_hosts=(),
        budget_limit=budget,
        evidence_target=_EVIDENCE_TARGET,
        live_transport_allowed=True,
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=10),
    )


def _auth(run_id: str, objective_id: str, capability: str):
    approval = ApprovalReceipt(
        principal_id="operator.local",
        run_id=run_id,
        goal_contract_id=objective_id,
        approved_capabilities=[capability],
        nonce="{0}.optin".format(run_id),
    )
    envelope = ApprovalEnvelope(
        envelope_id="{0}.env".format(run_id),
        capability_id=capability,
        approval_receipt_id="{0}.optin".format(run_id),
        predicted_effects=("perform one governed side effect",),
        reversibility=Reversibility.irreversible,
        risk=ActionRisk.high,
        budget=BudgetEnvelope(max_units=100, requested_units=1),
    )
    return {capability: (approval, envelope)}


def _dispatcher(ledger: SQLiteEvidenceLedger, capability: str, counter: list):
    descriptor = CapabilityDescriptor(
        capability_id=capability,
        name=capability.replace(".", "_"),
        risk=CapabilityRisk.high,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        side_effects=[SideEffect.network],
    )

    def handler(_payload):
        counter.append(1)
        return {"published": True}

    return GovernedExecutionDispatcher(
        capability_graph=CapabilityGraph((descriptor,)),
        handlers={capability: handler},
        ledger=ledger,
    )


def _blog_candidate(publish_capability: str) -> WorkflowCandidate:
    return WorkflowCandidate(
        candidate_id="blog.gated",
        nodes=(
            WorkflowNode(node_id="research", kind=NodeKind.llm_generic, produces_criteria=("topic",)),
            WorkflowNode(node_id="check", kind=NodeKind.verification, verifies_criteria=("topic",)),
            WorkflowNode(node_id="draft", kind=NodeKind.llm_generic, produces_criteria=("post",)),
            WorkflowNode(node_id="critic", kind=NodeKind.verification, verifies_criteria=("post",)),
            WorkflowNode(node_id="approve", kind=NodeKind.approval_gate),
            WorkflowNode(node_id="publish", kind=NodeKind.capability,
                         capability_ref=publish_capability, side_effect=SideEffectClass.public_write),
        ),
        edges=(
            WorkflowEdge(src="research", dst="check"),
            WorkflowEdge(src="check", dst="draft"),
            WorkflowEdge(src="draft", dst="critic"),
            WorkflowEdge(src="critic", dst="approve"),
            WorkflowEdge(src="approve", dst="publish"),
        ),
    )


def _runtime(tmp_path: Path, capability: str, counter: list, *, verifier=None, trust=None):
    ledger = SQLiteEvidenceLedger(tmp_path / "ev.sqlite3")
    store = WorkflowExecutionStateStore(tmp_path / "runs.sqlite3")
    dispatcher = _dispatcher(ledger, capability, counter)
    return WorkflowExecutionRuntime(
        dispatcher=dispatcher, ledger=ledger, state_store=store, trust_ledger=trust, verifier=verifier
    ), ledger


# --- The M1 DoD: suspend → resume → execute → evidence chain ----------------


def test_run_suspends_at_approval_gate_without_executing_publish(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    runtime, _ = _runtime(tmp_path, cap, counter)
    run = runtime.start(
        _blog_candidate(cap), lease=_lease("run.blog", "obj.blog", capability=cap),
        objective_id="obj.blog", required_criteria=("topic", "post"),
    )
    assert run.status is RunStatus.waiting_approval
    assert run.node_states["approve"] is NodeState.waiting_approval
    assert run.node_states["publish"] is NodeState.pending
    # The chokepoint holds: no side effect happened before approval.
    assert counter == []


def test_resume_executes_publish_and_completes_by_evidence(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    runtime, ledger = _runtime(tmp_path, cap, counter)
    lease = _lease("run.blog", "obj.blog", capability=cap)
    runtime.start(_blog_candidate(cap), lease=lease, objective_id="obj.blog",
                  required_criteria=("topic", "post"))
    run = runtime.resume("run.blog", lease=lease, approved_gates=("approve",), capability_approvals=_auth("run.blog", "obj.blog", cap))

    assert run.status is RunStatus.completed
    assert run.node_states["publish"] is NodeState.succeeded
    assert counter == [1]  # the publish handler ran exactly once, only after approval
    # Evidence chain is intact and the publish node traces back through approval.
    assert ledger.verify_chain().ok is True
    publish_event = _find_node_event(ledger, "publish")
    approve_record = _find_event(ledger, "approve", "approval_granted")
    # caused_by of publish includes the approval_granted event of 'approve'.
    payload = json.loads(str(publish_event["payload_json"]))
    assert approve_record["record_id"] in payload["caused_by"]


def test_publish_dispatch_is_the_only_path_to_side_effect(tmp_path) -> None:
    # Before resume the handler must never have run; the only route to execution
    # is dispatch-after-approval.
    cap = "mcp.blog.publish"
    counter: list = []
    runtime, _ = _runtime(tmp_path, cap, counter)
    lease = _lease("run.blog", "obj.blog", capability=cap)
    runtime.start(_blog_candidate(cap), lease=lease, objective_id="obj.blog")
    assert counter == []
    runtime.resume("run.blog", lease=lease, approved_gates=("approve",), capability_approvals=_auth("run.blog", "obj.blog", cap))
    assert counter == [1]


def test_trust_recorded_and_persisted(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    trust = TrustLedger(store=SQLiteTrustStatStore(tmp_path / "trust.sqlite3"))
    runtime, _ = _runtime(tmp_path, cap, counter, trust=trust)
    lease = _lease("run.blog", "obj.blog", capability=cap)
    runtime.start(_blog_candidate(cap), lease=lease, objective_id="obj.blog",
                  required_criteria=("topic", "post"))
    runtime.resume("run.blog", lease=lease, approved_gates=("approve",), capability_approvals=_auth("run.blog", "obj.blog", cap))
    # Earned trust for the publish capability survives in the persistent ledger.
    reopened = TrustLedger(store=SQLiteTrustStatStore(tmp_path / "trust.sqlite3"))
    assert reopened.stat(cap).success_count == 1


def test_idempotent_resume_does_not_rerun(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    runtime, _ = _runtime(tmp_path, cap, counter)
    lease = _lease("run.blog", "obj.blog", capability=cap)
    runtime.start(_blog_candidate(cap), lease=lease, objective_id="obj.blog",
                  required_criteria=("topic", "post"))
    runtime.resume("run.blog", lease=lease, approved_gates=("approve",), capability_approvals=_auth("run.blog", "obj.blog", cap))
    again = runtime.resume("run.blog", lease=lease, approved_gates=("approve",), capability_approvals=_auth("run.blog", "obj.blog", cap))
    assert again.status is RunStatus.completed
    assert counter == [1]  # not re-executed


# --- Failure → rollback receipts --------------------------------------------


def test_failure_rolls_back_prior_side_effects(tmp_path) -> None:
    cap = "sandbox.fs.write"
    counter: list = []
    candidate = WorkflowCandidate(
        candidate_id="write.then.verify",
        nodes=(
            WorkflowNode(node_id="approve", kind=NodeKind.approval_gate),
            WorkflowNode(node_id="write", kind=NodeKind.capability,
                         capability_ref=cap, side_effect=SideEffectClass.local_write),
            WorkflowNode(node_id="verify", kind=NodeKind.verification, verifies_criteria=("done",)),
        ),
        edges=(WorkflowEdge(src="approve", dst="write"), WorkflowEdge(src="write", dst="verify")),
    )
    runtime, ledger = _runtime(tmp_path, cap, counter, verifier=lambda node, _run: node.node_id != "verify")
    lease = _lease("run.w", "obj.w", capability=cap)
    runtime.start(candidate, lease=lease, objective_id="obj.w", required_criteria=("done",))
    run = runtime.resume("run.w", lease=lease, approved_gates=("approve",), capability_approvals=_auth("run.w", "obj.w", cap))

    assert run.status is RunStatus.failed
    assert run.node_states["verify"] is NodeState.failed
    # The write succeeded then got rolled back when the run failed.
    assert run.node_states["write"] is NodeState.rolled_back
    rollback_events = [r for r in ledger.records() if r["kind"] == "rollback"]
    assert len(rollback_events) == 1


# --- Guards: budget, gap ----------------------------------------------------


def test_over_budget_suspends(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    candidate = WorkflowCandidate(
        candidate_id="pricey",
        nodes=(
            WorkflowNode(node_id="a", kind=NodeKind.llm_generic, cost_units=5),
            WorkflowNode(node_id="b", kind=NodeKind.llm_generic, cost_units=20),
        ),
        edges=(WorkflowEdge(src="a", dst="b"),),
    )
    runtime, _ = _runtime(tmp_path, cap, counter)
    run = runtime.start(candidate, lease=_lease("run.p", "obj.p", capability=cap, budget=10),
                        objective_id="obj.p")
    assert run.status is RunStatus.blocked
    assert run.blocked_reason == "over_budget"


def test_gap_node_blocks_with_needs_connection(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    candidate = WorkflowCandidate(
        candidate_id="withgap",
        nodes=(
            WorkflowNode(node_id="research", kind=NodeKind.llm_generic),
            WorkflowNode(node_id="pub", kind=NodeKind.gap, missing_capability="mcp.tistory.publish"),
        ),
        edges=(WorkflowEdge(src="research", dst="pub"),),
    )
    runtime, _ = _runtime(tmp_path, cap, counter)
    run = runtime.start(candidate, lease=_lease("run.g", "obj.g", capability=cap), objective_id="obj.g")
    assert run.status is RunStatus.blocked
    assert run.blocked_reason == "needs_connection:mcp.tistory.publish"


# --- helpers ----------------------------------------------------------------


def _find_node_event(ledger: SQLiteEvidenceLedger, node_id: str) -> dict:

    for record in reversed(ledger.records()):
        if record["kind"] != "workflow_node":
            continue
        payload = json.loads(str(record["payload_json"]))
        if payload.get("node_id") == node_id:
            return record
    raise AssertionError("no event for node {0}".format(node_id))


def _find_event(ledger: SQLiteEvidenceLedger, node_id: str, status: str) -> dict:

    for record in ledger.records():
        if record["kind"] != "workflow_node":
            continue
        payload = json.loads(str(record["payload_json"]))
        if payload.get("node_id") == node_id and payload.get("status") == status:
            return record
    raise AssertionError("no {0} event for node {1}".format(status, node_id))


def test_resume_without_approving_gate_stays_suspended(tmp_path) -> None:
    # Bug fix: resuming with no approved gate must NOT clear the gate.
    cap = "mcp.blog.publish"
    counter: list = []
    runtime, _ = _runtime(tmp_path, cap, counter)
    lease = _lease("run.blog", "obj.blog", capability=cap)
    runtime.start(_blog_candidate(cap), lease=lease, objective_id="obj.blog",
                  required_criteria=("topic", "post"))
    run = runtime.resume("run.blog", lease=lease)  # no approved_gates
    assert run.status is RunStatus.waiting_approval
    assert run.node_states["publish"] is NodeState.pending
    assert counter == []  # nothing executed


def test_executed_with_error_is_a_failure_not_success(tmp_path) -> None:
    # Bug fix: a handler that runs but returns an error fails the workflow.
    cap = "mcp.blog.publish"
    ledger = SQLiteEvidenceLedger(tmp_path / "ev.sqlite3")
    descriptor = CapabilityDescriptor(
        capability_id=cap, name=cap.replace(".", "_"), risk=CapabilityRisk.high,
        input_schema={"type": "object"}, output_schema={"type": "object"},
        side_effects=[SideEffect.network],
    )
    dispatcher = GovernedExecutionDispatcher(
        capability_graph=CapabilityGraph((descriptor,)),
        handlers={cap: lambda _p: {"provider": "x", "error": "provider_transport_error"}},
        ledger=ledger,
    )
    trust = TrustLedger(store=SQLiteTrustStatStore(tmp_path / "trust.sqlite3"))
    runtime = WorkflowExecutionRuntime(
        dispatcher=dispatcher, ledger=ledger,
        state_store=WorkflowExecutionStateStore(tmp_path / "runs.sqlite3"), trust_ledger=trust,
    )
    lease = _lease("run.blog", "obj.blog", capability=cap)
    runtime.start(_blog_candidate(cap), lease=lease, objective_id="obj.blog",
                  required_criteria=("topic", "post"))
    run = runtime.resume("run.blog", lease=lease, approved_gates=("approve",),
                         capability_approvals=_auth("run.blog", "obj.blog", cap))
    assert run.status is RunStatus.failed
    assert run.blocked_reason == "tool_error:provider_transport_error"
    # Trust records a failure for the capability, not a success.
    assert trust.stat(cap).failure_count == 1
    assert trust.stat(cap).success_count == 0


def test_real_verifier_fails_when_criterion_not_produced(tmp_path) -> None:
    # A verification node that verifies a criterion NOTHING produces must FAIL —
    # completion is no longer self-asserted by merely declaring verifies_criteria.
    cap = "mcp.blog.publish"
    counter: list = []
    candidate = WorkflowCandidate(
        candidate_id="miswired",
        nodes=(
            WorkflowNode(node_id="draft", kind=NodeKind.llm_generic),  # produces nothing
            WorkflowNode(node_id="critic", kind=NodeKind.verification, verifies_criteria=("post",)),
        ),
        edges=(WorkflowEdge(src="draft", dst="critic"),),
    )
    runtime, _ = _runtime(tmp_path, cap, counter)
    run = runtime.start(candidate, lease=_lease("run.m", "obj.m", capability=cap),
                        objective_id="obj.m", required_criteria=("post",))
    assert run.status is RunStatus.failed
    assert run.node_states["critic"] is NodeState.failed


def test_real_verifier_passes_when_criterion_produced(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    candidate = WorkflowCandidate(
        candidate_id="wired",
        nodes=(
            WorkflowNode(node_id="draft", kind=NodeKind.llm_generic, produces_criteria=("post",)),
            WorkflowNode(node_id="critic", kind=NodeKind.verification, verifies_criteria=("post",)),
        ),
        edges=(WorkflowEdge(src="draft", dst="critic"),),
    )
    runtime, _ = _runtime(tmp_path, cap, counter)
    run = runtime.start(candidate, lease=_lease("run.w2", "obj.w2", capability=cap),
                        objective_id="obj.w2", required_criteria=("post",))
    assert run.status is RunStatus.completed


def test_verifier_checks_expected_artifacts_exist(tmp_path) -> None:
    cap = "mcp.blog.publish"
    counter: list = []
    missing = str(tmp_path / "nope.txt")
    candidate = WorkflowCandidate(
        candidate_id="artifact",
        nodes=(
            WorkflowNode(node_id="draft", kind=NodeKind.llm_generic, produces_criteria=("post",)),
            WorkflowNode(node_id="critic", kind=NodeKind.verification, verifies_criteria=("post",),
                         expected_artifacts=(missing,)),
        ),
        edges=(WorkflowEdge(src="draft", dst="critic"),),
    )
    runtime, _ = _runtime(tmp_path, cap, counter)
    run = runtime.start(candidate, lease=_lease("run.a", "obj.a", capability=cap),
                        objective_id="obj.a", required_criteria=("post",))
    # The declared artifact does not exist → verification fails.
    assert run.status is RunStatus.failed
