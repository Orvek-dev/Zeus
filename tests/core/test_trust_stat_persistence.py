from __future__ import annotations

from zeus_agent.trust_loop_runtime import (
    ActionRisk,
    BudgetEnvelope,
    Reversibility,
    SQLiteTrustStatStore,
    TrustLedger,
    TrustLoopAction,
)


def _action(capability_id: str) -> TrustLoopAction:
    return TrustLoopAction(
        action_id="act.{0}".format(capability_id.replace(".", "_")),
        run_id="run.1",
        goal_contract_id="goal.1",
        criterion_id="REQ-1:S1",
        capability_id=capability_id,
        risk=ActionRisk.low,
        reversibility=Reversibility.reversible,
        budget=BudgetEnvelope(max_units=4, requested_units=1),
    )


def test_in_memory_ledger_still_works_with_no_store() -> None:
    # Back-compat: the no-arg constructor stays in-memory.
    ledger = TrustLedger()
    action = _action("provider.fake.generate")
    for _ in range(3):
        ledger.record_success(action)
    assert ledger.propose_grant(action) is not None


def test_trust_survives_restart_with_store(tmp_path) -> None:
    # Given: a capability earns 3 clean successes through a persistent ledger.
    db = tmp_path / "trust" / "stats.sqlite3"
    action = _action("provider.fake.generate")
    first = TrustLedger(store=SQLiteTrustStatStore(db))
    for _ in range(3):
        first.record_success(action)

    # When: the process "restarts" — a brand-new ledger opens the same DB.
    second = TrustLedger(store=SQLiteTrustStatStore(db))

    # Then: the earned trust is still there (the autonomy leak is closed).
    stat = second.stat("provider.fake.generate")
    assert stat.success_count == 3
    assert stat.failure_count == 0
    assert second.propose_grant(action) is not None


def test_failure_persists_and_blocks_grant() -> None:
    # A recorded failure must also survive and keep the grant blocked.
    from tempfile import TemporaryDirectory
    from pathlib import Path

    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "stats.sqlite3"
        action = _action("mcp.unknown.tool")
        first = TrustLedger(store=SQLiteTrustStatStore(db))
        for _ in range(5):
            first.record_success(action)
        first.record_failure(action)

        second = TrustLedger(store=SQLiteTrustStatStore(db))
        stat = second.stat("mcp.unknown.tool")
        assert stat.success_count == 5
        assert stat.failure_count == 1
        # Any failure blocks the low-risk grant proposal.
        assert second.propose_grant(action) is None


def test_store_upsert_is_idempotent_on_capability_id(tmp_path) -> None:
    store = SQLiteTrustStatStore(tmp_path / "stats.sqlite3")
    store.upsert("cap.a", success_count=1, failure_count=0)
    store.upsert("cap.a", success_count=2, failure_count=1)
    assert store.get("cap.a") == (2, 1)
    assert store.all() == {"cap.a": (2, 1)}
    assert store.get("cap.missing") is None
