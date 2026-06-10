from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from zeus_agent.trust_loop_runtime import TrustDecision


class BudgetScope(str, Enum):
    run = "run"
    objective = "objective"
    fleet = "fleet"


class GovernorVerdict(BaseModel):
    """Pre-call enforcement outcome. Governors stop actions BEFORE they spend,
    they do not alert after the fact."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    allowed: bool
    forced_decision: Optional[TrustDecision] = None
    reason: str = "ok"


_OK = GovernorVerdict(allowed=True)


class BudgetGovernor:
    """Hard budget stops at run, objective, and fleet scope.

    Spend is charged from execution outcomes (actual cost), checked before
    every call (requested cost). Exhaustion is a DENY, not an ASK: an empty
    wallet is not a judgement call.
    """

    def __init__(self) -> None:
        self._limits: dict[tuple[str, str], int] = {}
        self._spent: dict[tuple[str, str], int] = {}

    def set_limit(self, scope: BudgetScope, scope_id: str, max_units: int) -> None:
        if max_units < 0:
            raise ValueError("budget_limit_negative")
        self._limits[(scope.value, scope_id)] = max_units

    def charge(self, scope: BudgetScope, scope_id: str, units: int) -> None:
        if units < 0:
            raise ValueError("budget_charge_negative")
        key = (scope.value, scope_id)
        self._spent[key] = self._spent.get(key, 0) + units

    def spent(self, scope: BudgetScope, scope_id: str) -> int:
        return self._spent.get((scope.value, scope_id), 0)

    def precall(
        self,
        *,
        requested_units: int,
        run_id: Optional[str] = None,
        objective_id: Optional[str] = None,
    ) -> GovernorVerdict:
        scopes: list[tuple[BudgetScope, str]] = [(BudgetScope.fleet, "fleet")]
        if run_id is not None:
            scopes.append((BudgetScope.run, run_id))
        if objective_id is not None:
            scopes.append((BudgetScope.objective, objective_id))
        for scope, scope_id in scopes:
            limit = self._limits.get((scope.value, scope_id))
            if limit is None:
                continue
            if self.spent(scope, scope_id) + max(requested_units, 0) > limit:
                return GovernorVerdict(
                    allowed=False,
                    forced_decision=TrustDecision.DENY,
                    reason="budget_exhausted_{0}".format(scope.value),
                )
        return _OK


class RateGovernor:
    """Sliding-window call rate per capability.

    A burst past the window forces ASK — unlike budget, a rate spike can be a
    legitimate workload, so a human gets the question instead of a hard stop.
    """

    def __init__(self, *, max_calls: int, window_seconds: int) -> None:
        if max_calls <= 0:
            raise ValueError("rate_max_calls_invalid")
        if window_seconds <= 0:
            raise ValueError("rate_window_invalid")
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._calls: dict[str, deque[datetime]] = {}

    def precall(self, capability_id: str, *, now: Optional[datetime] = None) -> GovernorVerdict:
        timestamp = now if now is not None else datetime.now(timezone.utc)
        window = self._calls.setdefault(capability_id, deque())
        while window and (timestamp - window[0]).total_seconds() >= self._window_seconds:
            window.popleft()
        if len(window) >= self._max_calls:
            return GovernorVerdict(
                allowed=False,
                forced_decision=TrustDecision.ASK,
                reason="rate_window_exceeded",
            )
        return _OK

    def record_call(self, capability_id: str, *, now: Optional[datetime] = None) -> None:
        timestamp = now if now is not None else datetime.now(timezone.utc)
        self._calls.setdefault(capability_id, deque()).append(timestamp)


class LoopGovernor:
    """Iteration cap and no-progress detection for agent loops.

    Progress is measured by a caller-supplied state hash: the same hash seen
    ``no_progress_limit`` times in a row means the loop is spinning, and the
    next call is parked for a human instead of burning budget.
    """

    def __init__(self, *, max_iterations: int = 50, no_progress_limit: int = 3) -> None:
        if max_iterations <= 0:
            raise ValueError("loop_max_iterations_invalid")
        if no_progress_limit <= 0:
            raise ValueError("loop_no_progress_limit_invalid")
        self._max_iterations = max_iterations
        self._no_progress_limit = no_progress_limit
        self._iterations: dict[str, int] = {}
        self._last_hash: dict[str, str] = {}
        self._repeats: dict[str, int] = {}

    def observe(self, run_id: str, *, state_hash: Optional[str] = None) -> GovernorVerdict:
        iterations = self._iterations.get(run_id, 0) + 1
        self._iterations[run_id] = iterations
        if iterations > self._max_iterations:
            return GovernorVerdict(
                allowed=False,
                forced_decision=TrustDecision.ASK,
                reason="loop_iteration_cap",
            )
        if state_hash is not None:
            if self._last_hash.get(run_id) == state_hash:
                repeats = self._repeats.get(run_id, 1) + 1
            else:
                repeats = 1
            self._last_hash[run_id] = state_hash
            self._repeats[run_id] = repeats
            if repeats >= self._no_progress_limit:
                return GovernorVerdict(
                    allowed=False,
                    forced_decision=TrustDecision.ASK,
                    reason="loop_no_progress",
                )
        return _OK


class GovernorBankConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    rate_max_calls: int = Field(default=30, gt=0)
    rate_window_seconds: int = Field(default=60, gt=0)
    loop_max_iterations: int = Field(default=50, gt=0)
    loop_no_progress_limit: int = Field(default=3, gt=0)


class GovernorBank:
    """The single pre-call checkpoint decide() consults (pipeline step 6).

    Order is deny-first: budget (DENY) before rate/loop (ASK), so the
    strictest verdict wins when several governors trip at once.
    """

    def __init__(self, config: Optional[GovernorBankConfig] = None) -> None:
        cfg = config if config is not None else GovernorBankConfig()
        self.budget = BudgetGovernor()
        self.rate = RateGovernor(
            max_calls=cfg.rate_max_calls,
            window_seconds=cfg.rate_window_seconds,
        )
        self.loop = LoopGovernor(
            max_iterations=cfg.loop_max_iterations,
            no_progress_limit=cfg.loop_no_progress_limit,
        )

    def precall(
        self,
        *,
        capability_id: str,
        requested_units: int,
        run_id: Optional[str] = None,
        objective_id: Optional[str] = None,
        state_hash: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> GovernorVerdict:
        budget = self.budget.precall(
            requested_units=requested_units,
            run_id=run_id,
            objective_id=objective_id,
        )
        if not budget.allowed:
            return budget
        rate = self.rate.precall(capability_id, now=now)
        if not rate.allowed:
            return rate
        if run_id is not None:
            loop = self.loop.observe(run_id, state_hash=state_hash)
            if not loop.allowed:
                return loop
        self.rate.record_call(capability_id, now=now)
        return _OK
