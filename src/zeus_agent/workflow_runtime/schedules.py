from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from zeus_agent.runtime_lease import RuntimeIntakeRequest, RuntimeLease, RuntimeLeaseBuilder

ScheduleDecision = Literal["planned", "idempotent_replay", "blocked"]


@dataclass(frozen=True)
class ScheduledObjectiveRequest:
    schedule_id: str
    objective_id: str
    cron_expression: str
    idempotency_key: str
    capability_id: str = "cron.schedule.tick"


@dataclass(frozen=True)
class ScheduledObjectiveRecord:
    schedule_id: str
    objective_id: str
    cron_expression: str
    idempotency_key: str
    cron_enabled: bool


@dataclass(frozen=True)
class SchedulePlanResult:
    decision: ScheduleDecision
    reason: str
    record: ScheduledObjectiveRecord | None
    handler_executed: bool = False
    network_opened: bool = False


class SchedulePlanLedger:
    def __init__(self) -> None:
        self._requests: dict[str, ScheduledObjectiveRequest] = {}
        self._records: dict[str, ScheduledObjectiveRecord] = {}

    def plan(
        self,
        *,
        request: ScheduledObjectiveRequest,
        lease: RuntimeLease | None,
        now: datetime,
    ) -> SchedulePlanResult:
        authorized = RuntimeLeaseBuilder().authorize(
            lease,
            RuntimeIntakeRequest(
                runtime_kind="cron",
                capability_id=request.capability_id,
                budget_required=1,
                evidence_target="mneme.wave13.production",
            ),
            now=now,
        )
        if authorized.decision == "blocked":
            return SchedulePlanResult(
                decision="blocked",
                reason=authorized.reason,
                record=None,
            )
        existing = self._requests.get(request.schedule_id)
        if existing == request:
            return SchedulePlanResult(
                decision="idempotent_replay",
                reason="duplicate_schedule_idempotent",
                record=self._records[request.schedule_id],
            )
        if existing is not None:
            return SchedulePlanResult(
                decision="blocked",
                reason="conflicting_schedule_replay",
                record=None,
            )
        record = ScheduledObjectiveRecord(
            schedule_id=request.schedule_id,
            objective_id=request.objective_id,
            cron_expression=request.cron_expression,
            idempotency_key=request.idempotency_key,
            cron_enabled=False,
        )
        self._requests[request.schedule_id] = request
        self._records[request.schedule_id] = record
        return SchedulePlanResult(
            decision="planned",
            reason="scheduled_objective_job_created",
            record=record,
        )
