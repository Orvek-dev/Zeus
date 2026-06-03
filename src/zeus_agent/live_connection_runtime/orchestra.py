from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict

from zeus_agent.orchestration_runtime import (
    ParallelSchedule,
    ParallelScheduler,
    ParallelTaskSpec,
)
from zeus_agent.runtime_lease import RuntimeLease

from .models import LiveConnectionPlan, LiveConnectionRequest
from .recovery import CleanupObligation, ReplayRequest, make_cleanup_obligation, make_replay_request
from .router import LiveConnectionRouter
from .trace import (
    LiveConnectionTrace,
    append_trace_decision,
    serialized_has_no_secret_echo,
    start_live_connection_trace,
)

OrchestraDecision = Literal["planned", "blocked"]


class LiveConnectionOrchestraPlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    decision: OrchestraDecision
    reason: str
    schedule: ParallelSchedule
    live_plan: LiveConnectionPlan
    trace: LiveConnectionTrace
    replay_request: Optional[ReplayRequest] = None
    cleanup_obligation: Optional[CleanupObligation] = None
    blocked_reasons: tuple[str, ...]
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False


class LiveConnectionOrchestraPlanner:
    def __init__(
        self,
        scheduler: Optional[ParallelScheduler] = None,
        router: Optional[LiveConnectionRouter] = None,
    ) -> None:
        self._scheduler = scheduler or ParallelScheduler()
        self._router = router or LiveConnectionRouter()

    def plan(
        self,
        tasks: Sequence[ParallelTaskSpec],
        requests: Sequence[LiveConnectionRequest],
        *,
        runtime_lease: Optional[RuntimeLease],
        objective_contract_bound: bool = True,
        trace_id: str = "trace.live_connection_orchestra",
        now: Optional[datetime] = None,
    ) -> LiveConnectionOrchestraPlan:
        schedule = self._scheduler.plan(tasks)
        trace = append_trace_decision(
            start_live_connection_trace(trace_id),
            step_id="step.orchestra.schedule",
            decision=schedule.decision,
            reason=schedule.reason,
        )
        if schedule.decision == "blocked":
            return _orchestra_result(
                decision="blocked",
                reason="parallel_schedule_blocked",
                schedule=schedule,
                live_plan=_empty_blocked_live_plan(schedule.blocked_reasons),
                trace=trace,
                replay_request=make_replay_request(
                    trace,
                    replay_id="replay.orchestra.schedule",
                    from_step_id="step.orchestra.schedule",
                    reason="retry after schedule blocker resolution",
                ),
                cleanup_obligation=None,
            )

        live_plan = self._router.plan(
            requests,
            runtime_lease=runtime_lease,
            objective_contract_bound=objective_contract_bound,
            now=now,
        )
        trace = append_trace_decision(
            trace,
            step_id="step.live_connection.routes",
            decision=live_plan.decision,
            reason=live_plan.decision,
        )
        cleanup = make_cleanup_obligation(
            trace,
            obligation_id="cleanup.live_connection_orchestra",
            step_id="step.live_connection.routes",
            reason="remove staged orchestration evidence after review",
        )
        replay = (
            make_replay_request(
                trace,
                replay_id="replay.live_connection.routes",
                from_step_id="step.live_connection.routes",
                reason="retry after lease, source, or security correction",
            )
            if live_plan.decision == "blocked"
            else None
        )
        return _orchestra_result(
            decision=live_plan.decision,
            reason="orchestra_live_connection_{0}".format(live_plan.decision),
            schedule=schedule,
            live_plan=live_plan,
            trace=trace,
            replay_request=replay,
            cleanup_obligation=cleanup,
        )


def plan_live_connection_orchestra(
    tasks: Sequence[ParallelTaskSpec],
    requests: Sequence[LiveConnectionRequest],
    *,
    runtime_lease: Optional[RuntimeLease],
    objective_contract_bound: bool = True,
    now: Optional[datetime] = None,
) -> LiveConnectionOrchestraPlan:
    return LiveConnectionOrchestraPlanner().plan(
        tasks,
        requests,
        runtime_lease=runtime_lease,
        objective_contract_bound=objective_contract_bound,
        now=now,
    )


def _orchestra_result(
    *,
    decision: OrchestraDecision,
    reason: str,
    schedule: ParallelSchedule,
    live_plan: LiveConnectionPlan,
    trace: LiveConnectionTrace,
    replay_request: Optional[ReplayRequest],
    cleanup_obligation: Optional[CleanupObligation],
) -> LiveConnectionOrchestraPlan:
    blocked_reasons = _merge_reasons(schedule.blocked_reasons, live_plan.blocked_reasons)
    result = LiveConnectionOrchestraPlan(
        decision=decision,
        reason=reason,
        schedule=schedule,
        live_plan=live_plan,
        trace=trace,
        replay_request=replay_request,
        cleanup_obligation=cleanup_obligation,
        blocked_reasons=blocked_reasons,
        handler_executed=schedule.handler_executed or live_plan.handler_executed,
        network_opened=schedule.network_opened or live_plan.network_opened,
        no_secret_echo=schedule.dry_run and live_plan.no_secret_echo and trace.no_secret_echo,
        live_production_claimed=False,
    )
    serialized = result.model_dump_json()
    if not serialized_has_no_secret_echo(serialized):
        return result.model_copy(update={"no_secret_echo": False})
    return result


def _empty_blocked_live_plan(reasons: tuple[str, ...]) -> LiveConnectionPlan:
    return LiveConnectionPlan(
        decision="blocked",
        routes=(),
        audit_record_created=True,
        handler_executed=False,
        network_opened=False,
        no_secret_echo=True,
        blocked_reasons=reasons or ("parallel_schedule_blocked",),
    )


def _merge_reasons(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for reason in (*left, *right):
        if reason not in merged:
            merged.append(reason)
    return tuple(merged)


__all__ = [
    "LiveConnectionOrchestraPlan",
    "LiveConnectionOrchestraPlanner",
    "OrchestraDecision",
    "plan_live_connection_orchestra",
]
