"""P7 conformance — loop governance.

budget-hardstop-mid-loop, no-progress-pause, deadman-demotes,
novelty-escalates, fleet-ceiling-trips (+ standing-lease renewal, quiet
hours, drift report). Pre-call enforcement, never after-the-fact alerts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from zeus_agent.adapters.claude_code_hook import ControlPlaneState
from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    Obligation,
)
from zeus_agent.digest_runtime import ack_digest
from zeus_agent.governor_runtime import BudgetScope
from zeus_agent.loop_runtime import (
    StandingLease,
    apply_quiet_hours,
    check_deadman,
    drift_report,
    in_quiet_hours,
    lease_load,
    lease_renew,
    lease_save,
    restore_autonomy,
)
from zeus_agent.proxy_runtime import seed_proxy_capability_store
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    SQLiteControlPlaneStore,
    TrustDecision,
)

NOW = datetime(2026, 6, 11, 14, 0, tzinfo=timezone.utc)


def _request(
    capability_id: str,
    *,
    run_id: str = "run.loop",
    objective_id: str | None = None,
    state_hash: str | None = None,
    args: dict | None = None,
) -> DecisionRequest:
    return DecisionRequest(
        principal_id="agent.loop",
        session_id="loop.sess",
        run_id=run_id,
        capability_id=capability_id,
        args=args or {},
        requested_units=2,
        context=DecisionContext(
            host=HostKind.console,
            surface=GateSurface.console,
            objective_id=objective_id,
            state_hash=state_hash,
        ),
    )


def _engine(tmp_path: Path):
    state = ControlPlaneState(tmp_path / "zeus")
    return (
        state.build_engine(capabilities=seed_proxy_capability_store()),
        SQLiteControlPlaneStore(state.state_path),
        state,
    )


# ----------------------------------------------------- budget-hardstop-mid-loop
def test_budget_hardstop_mid_loop(tmp_path: Path) -> None:
    engine, store, _state = _engine(tmp_path)
    store.set_budget_limit("objective", "obj.loop", 10)
    spent_iterations = 0
    for _ in range(10):
        response = engine.decide(_request("fs.read", objective_id="obj.loop"))
        if response.decision is TrustDecision.DENY:
            break
        engine.record(
            response.receipt_id,
            ExecutionOutcome(status=ExecutionStatus.success, cost_actual_units=3),
            objective_id="obj.loop",
        )
        spent_iterations += 1
    assert response.decision is TrustDecision.DENY
    assert response.reason == "budget_exhausted_objective"
    assert spent_iterations == 3  # 3×3=9 spent; the 4th call (9+2>10) is stopped


# ------------------------------------------------------------ no-progress-pause
def test_no_progress_pause_on_identical_state_hash(tmp_path: Path) -> None:
    engine, _store, _state = _engine(tmp_path)
    decisions = [
        engine.decide(_request("fs.read", run_id="run.spin", state_hash="h.same"))
        for _ in range(3)
    ]
    assert [d.decision for d in decisions[:2]] == [TrustDecision.AUTO, TrustDecision.AUTO]
    assert decisions[2].decision is TrustDecision.ASK
    assert decisions[2].reason == "loop_no_progress"


# -------------------------------------------------------------- deadman-demotes
def test_deadman_unacked_digest_demotes_autonomy(tmp_path: Path) -> None:
    engine, store, state = _engine(tmp_path)
    ack_digest(store, now=NOW - timedelta(days=30))
    verdict = check_deadman(store, now=NOW)
    assert verdict["demoted"] is True

    # demotion binds the NEXT engine process pre-call (not a notification)
    demoted_engine = state.build_engine(capabilities=seed_proxy_capability_store())
    asked = demoted_engine.decide(_request("fs.write", args={"path": "/w/a"}))
    assert asked.decision is TrustDecision.ASK
    assert asked.reason == "deadman_unacked_digest"
    # reads stay alive — demotion is about side effects
    read = demoted_engine.decide(_request("fs.read"))
    assert read.decision is TrustDecision.AUTO

    # acking the digest restores autonomy
    ack_digest(store, now=NOW)
    restore_autonomy(store)
    assert check_deadman(store, now=NOW)["demoted"] is False
    restored = state.build_engine(capabilities=seed_proxy_capability_store())
    again = restored.decide(_request("fs.write", args={"path": "/w/a"}))
    assert again.reason != "deadman_unacked_digest"


# ------------------------------------------------------------ novelty-escalates
def test_novelty_first_seen_host_escalates_once(tmp_path: Path) -> None:
    engine, _store, state = _engine(tmp_path)
    first = engine.decide(
        _request("web.fetch", args={"url": "https://newhost.example/x", "network_host": "newhost.example"})
    )
    assert first.decision is TrustDecision.ASK
    assert first.reason == "novelty_first_seen_network_host"

    # learned — and learned PERSISTENTLY: a fresh process does not re-ask
    fresh = state.build_engine(capabilities=seed_proxy_capability_store())
    second = fresh.decide(
        _request("web.fetch", args={"url": "https://newhost.example/y", "network_host": "newhost.example"})
    )
    assert second.decision is TrustDecision.AUTO


# ---------------------------------------------------------- fleet-ceiling-trips
def test_fleet_ceiling_trips_across_objectives(tmp_path: Path) -> None:
    engine, store, _state = _engine(tmp_path)
    store.set_budget_limit("fleet", "fleet", 10)
    first = engine.decide(_request("fs.read", objective_id="obj.a"))
    engine.record(
        first.receipt_id, ExecutionOutcome(status=ExecutionStatus.success, cost_actual_units=9)
    )
    denied = engine.decide(_request("fs.read", objective_id="obj.b"))
    assert denied.decision is TrustDecision.DENY
    assert denied.reason == "budget_exhausted_fleet"
    assert engine.governors.budget.spent(BudgetScope.fleet, "fleet") == 9


# ------------------------------------------------------- standing lease renewal
def test_standing_lease_renewal_checkpoint(tmp_path: Path) -> None:
    _engine_, store, _state = _engine(tmp_path)
    lease = StandingLease(
        lease_id="weekly.report",
        objective_id="obj.report",
        cadence_days=7,
        last_renewed_at=NOW - timedelta(days=8),
    )
    lease_save(store, lease)
    loaded = lease_load(store, "weekly.report")
    assert loaded is not None
    assert loaded.renewal_due(now=NOW) is True  # next run must checkpoint a human
    renewed = lease_renew(store, loaded, now=NOW)
    assert renewed.renewal_due(now=NOW) is False
    assert lease_load(store, "weekly.report").last_renewed_at == NOW


# ----------------------------------------------------------------- quiet hours
def test_quiet_hours_hold_asks_for_the_morning(tmp_path: Path) -> None:
    engine, _store, _state = _engine(tmp_path)
    asked = engine.decide(_request("fs.write", args={"path": "/w/a"}))
    assert asked.decision is TrustDecision.ASK

    night = NOW.replace(hour=23)
    held = apply_quiet_hours(asked, now=night, spec="22-07")
    assert Obligation.quiet_hold in held.obligations
    assert held.parked_action_id == asked.parked_action_id  # still parked, fail-closed

    day = NOW.replace(hour=14)
    untouched = apply_quiet_hours(asked, now=day, spec="22-07")
    assert Obligation.quiet_hold not in untouched.obligations
    assert in_quiet_hours(NOW.replace(hour=2), "22-07") is True
    assert in_quiet_hours(NOW.replace(hour=12), "22-07") is False


# ------------------------------------------------------------------ drift watch
def test_drift_report_flags_novel_capability_mix(tmp_path: Path) -> None:
    engine, _store, _state = _engine(tmp_path)
    engine.decide(_request("fs.read"))
    report = drift_report(engine.recorder, now=datetime.now(timezone.utc))
    assert report["current_actions"] >= 1
    assert report["previous_actions"] == 0
    assert report["drift_score"] == 0.0  # empty prior window → no judgement
