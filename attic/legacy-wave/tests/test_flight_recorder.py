from __future__ import annotations

from pathlib import Path

from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    FlightRecorder,
    GovernedLedgerReader,
    LedgerPrincipalKind,
    SQLiteEvidenceLedger,
)

RUN = "run.flight.test"


def _recorder(tmp_path: Path) -> FlightRecorder:
    return FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3"))


def test_outcome_links_decision_via_caused_by(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    decision = recorder.record_decision(
        run_id=RUN,
        payload={"capability_id": "fs.write", "decision": "auto", "session_id": "s1"},
    )
    outcome = recorder.record_outcome(
        run_id=RUN,
        outcome=ExecutionOutcome(status=ExecutionStatus.success, cost_actual_units=3),
        caused_by=(decision.record_id,),
    )
    chain = recorder.why(outcome.record_id)
    assert [str(record["record_id"]) for record in chain] == [
        outcome.record_id,
        decision.record_id,
    ]


def test_why_walks_multi_hop_chain(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    fetch_decision = recorder.record_decision(
        run_id=RUN, payload={"capability_id": "web.fetch", "session_id": "s1"}
    )
    fetch_outcome = recorder.record_outcome(
        run_id=RUN,
        outcome=ExecutionOutcome(status=ExecutionStatus.success),
        caused_by=(fetch_decision.record_id,),
    )
    send_decision = recorder.record_decision(
        run_id=RUN,
        payload={"capability_id": "mail.send", "session_id": "s1"},
        caused_by=(fetch_outcome.record_id,),
    )
    chain = recorder.why(send_decision.record_id)
    ids = [str(record["record_id"]) for record in chain]
    assert ids == [send_decision.record_id, fetch_outcome.record_id, fetch_decision.record_id]


def test_failure_and_rollback_receipts_recorded(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    decision = recorder.record_decision(run_id=RUN, payload={"capability_id": "vcs.push"})
    failure = recorder.record_outcome(
        run_id=RUN,
        outcome=ExecutionOutcome(status=ExecutionStatus.failure, notes="remote rejected"),
        caused_by=(decision.record_id,),
    )
    rollback = recorder.record_rollback(
        run_id=RUN,
        plan_id="undo.plan.1",
        status=ExecutionStatus.success,
        caused_by=(failure.record_id,),
    )
    kinds = [str(record["kind"]) for record in recorder.ledger.records()]
    assert kinds == ["decision_receipt", "execution_outcome", "rollback_receipt"]
    chain = recorder.why(rollback.record_id)
    assert len(chain) == 3


def test_coverage_counts_governed_share(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    decision = recorder.record_decision(run_id=RUN, payload={"capability_id": "fs.read"})
    recorder.record_gate_observation(
        run_id=RUN,
        host="claude_code",
        surface="hook",
        capability_id="fs.read",
        governed=True,
        decision_receipt_record_id=decision.record_id,
    )
    recorder.record_gate_observation(
        run_id=RUN,
        host="claude_code",
        surface="hook",
        capability_id="terminal.run",
        governed=False,
    )
    coverage = recorder.coverage()
    assert coverage.observed == 2
    assert coverage.governed == 1
    assert coverage.decisions == 1
    assert coverage.governed_pct == 0.5


def test_coverage_with_no_observations_is_none(tmp_path: Path) -> None:
    assert _recorder(tmp_path).coverage().governed_pct is None


def test_chain_still_verifies_with_new_kinds(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    decision = recorder.record_decision(run_id=RUN, payload={"capability_id": "fs.read"})
    recorder.record_outcome(
        run_id=RUN,
        outcome=ExecutionOutcome(status=ExecutionStatus.error),
        caused_by=(decision.record_id,),
    )
    assert recorder.ledger.verify_chain().ok


def test_user_read_is_full_and_unrecorded(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    recorder.record_decision(run_id=RUN, payload={"session_id": "s1", "trust_score": 0.9})
    reader = GovernedLedgerReader(recorder)
    result = reader.read(principal_kind=LedgerPrincipalKind.user, principal_id="operator.local")
    assert result.scope == "full"
    assert len(result.records) == 1
    assert len(recorder.ledger.records()) == 1  # no meta-receipt for console reads


def test_agent_read_is_session_scoped_masked_and_audited(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    recorder.record_decision(
        run_id=RUN,
        payload={"session_id": "s1", "capability_id": "fs.read", "trust_score": 0.9},
    )
    recorder.record_decision(
        run_id=RUN,
        payload={"session_id": "s2", "capability_id": "mail.send"},
    )
    reader = GovernedLedgerReader(recorder)
    result = reader.read(
        principal_kind=LedgerPrincipalKind.agent,
        principal_id="agent.subprocess",
        session_id="s1",
    )
    assert result.scope == "session"
    assert len(result.records) == 1
    payload = result.records[0]["payload"]
    assert payload["capability_id"] == "fs.read"
    assert "trust_score" not in payload  # policy internals never agent-readable
    assert result.taint_label == "untrusted"
    kinds = [str(record["kind"]) for record in recorder.ledger.records()]
    assert kinds[-1] == "ledger_read"  # the read itself left a receipt
    assert result.read_receipt_record_id is not None


def test_agent_read_without_session_is_blocked(tmp_path: Path) -> None:
    reader = GovernedLedgerReader(_recorder(tmp_path))
    result = reader.read(principal_kind=LedgerPrincipalKind.agent, principal_id="agent.x")
    assert result.decision == "blocked"
    assert result.blocked_reason == "agent_read_requires_session_scope"


def test_agent_cannot_see_ledger_read_meta_records(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    recorder.record_decision(run_id=RUN, payload={"session_id": "s1"})
    reader = GovernedLedgerReader(recorder)
    reader.read(
        principal_kind=LedgerPrincipalKind.agent, principal_id="agent.x", session_id="s1"
    )
    second = reader.read(
        principal_kind=LedgerPrincipalKind.agent, principal_id="agent.x", session_id="s1"
    )
    kinds = {str(record["kind"]) for record in second.records}
    assert "ledger_read" not in kinds


def test_record_by_id_point_lookup_hit_and_miss(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    decision = recorder.record_decision(
        run_id=RUN, payload={"capability_id": "fs.read", "session_id": "s1"}
    )
    found = recorder.ledger.record_by_id(decision.record_id)
    assert found is not None
    assert str(found["record_id"]) == decision.record_id
    assert str(found["kind"]) == "decision_receipt"
    assert recorder.ledger.record_by_id("trust.ev.999999") is None
