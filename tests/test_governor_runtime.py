from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zeus_agent.governor_runtime import (
    BudgetGovernor,
    BudgetScope,
    GovernorBank,
    GovernorBankConfig,
    LoopGovernor,
    RateGovernor,
)
from zeus_agent.trust_loop_runtime import TrustDecision

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


def test_budget_precall_denies_when_exhausted() -> None:
    governor = BudgetGovernor()
    governor.set_limit(BudgetScope.run, "run.1", 100)
    governor.charge(BudgetScope.run, "run.1", 90)
    verdict = governor.precall(requested_units=20, run_id="run.1")
    assert not verdict.allowed
    assert verdict.forced_decision is TrustDecision.DENY
    assert verdict.reason == "budget_exhausted_run"


def test_budget_precall_allows_within_envelope() -> None:
    governor = BudgetGovernor()
    governor.set_limit(BudgetScope.run, "run.1", 100)
    governor.charge(BudgetScope.run, "run.1", 90)
    assert governor.precall(requested_units=10, run_id="run.1").allowed


def test_budget_objective_scope_is_independent_of_run() -> None:
    governor = BudgetGovernor()
    governor.set_limit(BudgetScope.objective, "obj.1", 50)
    governor.charge(BudgetScope.objective, "obj.1", 50)
    verdict = governor.precall(requested_units=1, run_id="run.1", objective_id="obj.1")
    assert verdict.reason == "budget_exhausted_objective"


def test_budget_without_limit_is_open() -> None:
    governor = BudgetGovernor()
    assert governor.precall(requested_units=10_000, run_id="run.unbudgeted").allowed


def test_rate_window_forces_ask() -> None:
    governor = RateGovernor(max_calls=2, window_seconds=60)
    assert governor.precall("mail.send", now=NOW).allowed
    governor.record_call("mail.send", now=NOW)
    governor.record_call("mail.send", now=NOW + timedelta(seconds=1))
    verdict = governor.precall("mail.send", now=NOW + timedelta(seconds=2))
    assert not verdict.allowed
    assert verdict.forced_decision is TrustDecision.ASK


def test_rate_window_slides() -> None:
    governor = RateGovernor(max_calls=2, window_seconds=60)
    governor.record_call("mail.send", now=NOW)
    governor.record_call("mail.send", now=NOW + timedelta(seconds=1))
    assert governor.precall("mail.send", now=NOW + timedelta(seconds=61)).allowed


def test_loop_iteration_cap() -> None:
    governor = LoopGovernor(max_iterations=3, no_progress_limit=99)
    for _ in range(3):
        assert governor.observe("run.loop").allowed
    verdict = governor.observe("run.loop")
    assert not verdict.allowed
    assert verdict.reason == "loop_iteration_cap"


def test_loop_no_progress_state_hash() -> None:
    governor = LoopGovernor(max_iterations=99, no_progress_limit=3)
    assert governor.observe("run.loop", state_hash="aaaa").allowed
    assert governor.observe("run.loop", state_hash="aaaa").allowed
    verdict = governor.observe("run.loop", state_hash="aaaa")
    assert not verdict.allowed
    assert verdict.reason == "loop_no_progress"


def test_loop_progress_resets_repeat_counter() -> None:
    governor = LoopGovernor(max_iterations=99, no_progress_limit=2)
    assert governor.observe("run.loop", state_hash="aaaa").allowed
    assert governor.observe("run.loop", state_hash="bbbb").allowed
    assert governor.observe("run.loop", state_hash="cccc").allowed


def test_bank_orders_budget_before_rate() -> None:
    bank = GovernorBank(GovernorBankConfig(rate_max_calls=1, rate_window_seconds=60))
    bank.budget.set_limit(BudgetScope.run, "run.1", 0)
    verdict = bank.precall(
        capability_id="mail.send",
        requested_units=1,
        run_id="run.1",
        now=NOW,
    )
    assert verdict.forced_decision is TrustDecision.DENY


def test_bank_allows_and_records_rate() -> None:
    bank = GovernorBank(GovernorBankConfig(rate_max_calls=1, rate_window_seconds=60))
    first = bank.precall(capability_id="mail.send", requested_units=1, run_id="run.1", now=NOW)
    assert first.allowed
    second = bank.precall(
        capability_id="mail.send",
        requested_units=1,
        run_id="run.1",
        now=NOW + timedelta(seconds=1),
    )
    assert second.forced_decision is TrustDecision.ASK
