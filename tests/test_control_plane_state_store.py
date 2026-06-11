"""GAP-1: budget counters, approval queue, and the decision sequence must
survive process exit. Each engine instance below stands in for a fresh
one-decision gate process sharing the same control-plane home."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeus_agent.adapters.claude_code_hook import (
    ControlPlaneState,
    run_hook_event,
    seed_capability_store,
)
from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)
from zeus_agent.governor_runtime import BudgetScope, GovernorBank
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    FlightRecorder,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
    TrustDecision,
)


def _engine(tmp_path: Path) -> ZeusDecisionEngine:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")
    return ZeusDecisionEngine(
        recorder=FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3")),
        capabilities=seed_capability_store(),
        governors=GovernorBank(budget_store=store),
        queue=SQLiteApprovalQueue(store),
        seq_counter=lambda: store.next_counter("decision_seq"),
    )


def _read_request(run_id: str) -> DecisionRequest:
    return DecisionRequest(
        principal_id="agent.test",
        session_id="sess-persist",
        run_id=run_id,
        capability_id="fs.read",
        requested_units=3,
        context=DecisionContext(host=HostKind.console, surface=GateSurface.console),
    )


def test_budget_spend_survives_process_restart(tmp_path: Path) -> None:
    first = _engine(tmp_path)
    first.governors.budget.set_limit(BudgetScope.fleet, "fleet", 5)
    response = first.decide(_read_request("run.p.1"))
    assert response.decision is TrustDecision.AUTO
    first.record(response.receipt_id, ExecutionOutcome(status=ExecutionStatus.success, cost_actual_units=4))

    # a brand-new engine over the same home must see the 4 units already spent
    second = _engine(tmp_path)
    assert second.governors.budget.spent(BudgetScope.fleet, "fleet") == 4
    denied = second.decide(_read_request("run.p.2"))
    assert denied.decision is TrustDecision.DENY
    assert denied.reason == "budget_exhausted_fleet"


def test_parked_ask_visible_to_later_process(tmp_path: Path) -> None:
    first = _engine(tmp_path)
    asked = first.decide(
        DecisionRequest(
            principal_id="agent.test",
            session_id="sess-persist",
            run_id="run.p.3",
            capability_id="mail.send",
            context=DecisionContext(host=HostKind.console, surface=GateSurface.console),
        )
    )
    assert asked.decision is TrustDecision.ASK
    assert asked.parked_action_id is not None

    second = _engine(tmp_path)
    pending = second.queue.pending(now=datetime.now(timezone.utc))
    assert [parked.parked_action_id for parked in pending] == [asked.parked_action_id]
    assert second.queue.get(asked.parked_action_id).action.capability_id == "mail.send"

    # TTL expiry is enforced by the store, not by who parked it
    expired = second.queue.pending(now=datetime.now(timezone.utc) + timedelta(seconds=601))
    assert expired == ()
    assert second.queue.get(asked.parked_action_id).status == "expired"


def test_decision_seq_unique_across_processes(tmp_path: Path) -> None:
    ids = []
    for index in range(2):
        engine = _engine(tmp_path)  # fresh process each decision
        response = engine.decide(
            DecisionRequest(
                principal_id="agent.test",
                session_id="sess-persist",
                run_id="run.p.4",
                capability_id="mail.send",
                context=DecisionContext(host=HostKind.console, surface=GateSurface.console),
            )
        )
        assert response.parked_action_id is not None, "iteration {0}".format(index)
        ids.append(response.parked_action_id)
    assert len(set(ids)) == 2
    # second park supersedes nothing: distinct action ids → both rows kept,
    # and the earlier one is still readable for the audit trail
    first_engine = _engine(tmp_path)
    assert first_engine.queue.get(ids[0]).action.action_id != first_engine.queue.get(ids[1]).action.action_id


def test_hook_processes_share_state_db(tmp_path: Path) -> None:
    home = tmp_path / "zeus"
    payload = {
        "session_id": "sess-hook",
        "tool_name": "Read",
        "tool_input": {"file_path": "/work/a.py"},
        "cwd": "/work",
    }
    # two fully separate gate invocations (fresh ControlPlaneState each)
    run_hook_event(ControlPlaneState(home), "pre", dict(payload))
    run_hook_event(ControlPlaneState(home), "pre", dict(payload))
    store = SQLiteControlPlaneStore(home / "control-plane" / "state.sqlite3")
    # both processes drew from the same persistent decision sequence
    assert store.next_counter("decision_seq") == 3


def test_once_grant_burn_survives_at_every_gate(tmp_path: Path) -> None:
    """The burn used to persist only because the Claude hook remembered to
    save. The write-through store makes consume() durable at the ENGINE
    level, so hermes/openclaw/gateway processes (any build_engine caller)
    get it too — no per-gate persistence calls to forget."""
    from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

    home = tmp_path / "zeus"
    ControlPlaneState(home).add_grant(
        issue_grant(
            grant_id="grant.once.crossgate",
            capability_id="fs.write",
            scope=GrantScope.once,
            session_id="sess-hermes",
        )
    )

    def _decide_once() -> TrustDecision:
        engine = ControlPlaneState(home).build_engine()  # fresh gate process
        return engine.decide(
            DecisionRequest(
                principal_id="agent.hermes",
                session_id="sess-hermes",
                run_id="run.hermes.1",
                capability_id="fs.write",
                context=DecisionContext(host=HostKind.hermes, surface=GateSurface.hook),
            )
        ).decision

    assert _decide_once() is TrustDecision.AUTO  # covered, burned, PERSISTED
    assert _decide_once() is TrustDecision.ASK, "a spent once-grant must not re-fire"


def test_expired_park_can_never_resolve_approved(tmp_path: Path) -> None:
    """An approval that races past the TTL must fail closed — resolve()
    re-checks expiry itself instead of trusting a prior sweep."""
    engine = _engine(tmp_path)
    asked = engine.decide(
        DecisionRequest(
            principal_id="agent.test",
            session_id="sess-ttl",
            run_id="run.ttl",
            capability_id="mail.send",
            context=DecisionContext(host=HostKind.console, surface=GateSurface.console),
        )
    )
    assert asked.parked_action_id is not None
    late = datetime.now(timezone.utc) + timedelta(seconds=601)  # past the 600s TTL

    # approve AFTER the deadline, with no expiry sweep having run first
    resolved = engine.queue.resolve(asked.parked_action_id, approved=True, now=late)
    assert resolved.status == "expired"
    assert engine.queue.get(asked.parked_action_id).status == "expired"
    # and it stays dead: a second approval attempt cannot revive it
    again = engine.queue.resolve(asked.parked_action_id, approved=True, now=late)
    assert again.status == "expired"


def test_store_counters_and_budget_roundtrip(tmp_path: Path) -> None:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")
    assert store.next_counter("x") == 1
    assert store.next_counter("x") == 2
    assert store.budget_limit("run", "r1") is None
    store.set_budget_limit("run", "r1", 10)
    store.set_budget_limit("run", "r1", 7)  # update, not duplicate
    assert store.budget_limit("run", "r1") == 7
    store.add_budget_spend("run", "r1", 3)
    store.add_budget_spend("run", "r1", 2)
    assert store.budget_spent("run", "r1") == 5
    assert json.loads("{}") == {}  # keep json import honest
