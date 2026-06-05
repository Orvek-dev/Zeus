from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zeus_agent.runtime_lease import RuntimeIntakeRequest, RuntimeLease, RuntimeLeaseBuilder
from zeus_agent.security.credentials import redact_secret_spans

StandingOrderDecision = Literal["planned", "idempotent_replay", "blocked"]
_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class StandingOrderRequest(BaseModel):
    model_config = _MODEL_CONFIG

    standing_order_id: str
    objective: str
    cron_expression: str
    idempotency_key: str
    evidence_target: str
    destructive_action_requested: bool = False
    live_delivery_requested: bool = False
    delivery_targets: tuple[str, ...] = ()
    approval_receipt_id: Optional[str] = None
    max_ticks_per_window: int = Field(default=1, ge=1)

    @field_validator(
        "standing_order_id",
        "objective",
        "cron_expression",
        "idempotency_key",
        "evidence_target",
    )
    @classmethod
    def _non_empty(cls, value: str) -> str:
        normalized = redact_secret_spans(value)
        if not normalized:
            raise ValueError("standing_order_field_empty")
        return normalized

    @field_validator("cron_expression")
    @classmethod
    def _cron_has_five_fields(cls, value: str) -> str:
        if len(value.split()) != 5:
            raise ValueError("cron_expression_must_have_five_fields")
        return value

    @field_validator("delivery_targets")
    @classmethod
    def _redact_delivery_targets(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(redact_secret_spans(value) for value in values if value.strip())

    @field_validator("approval_receipt_id")
    @classmethod
    def _redact_approval(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        redacted = redact_secret_spans(value)
        return redacted or None


class StandingOrderRecord(BaseModel):
    model_config = _MODEL_CONFIG

    standing_order_id: str
    objective: str
    cron_expression: str
    idempotency_key: str
    evidence_target: str
    cron_enabled: bool = False
    recurrence_guard_enabled: bool = True
    live_delivery_allowed: bool = False
    delivery_targets: tuple[str, ...] = ()


class StandingOrderPlanResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: StandingOrderDecision
    reason: str
    reasons: tuple[str, ...]
    record: Optional[StandingOrderRecord] = None
    handler_executed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True


class StandingOrderRuntime:
    def __init__(self) -> None:
        self._requests: dict[str, StandingOrderRequest] = {}
        self._records: dict[str, StandingOrderRecord] = {}

    def plan(
        self,
        *,
        request: StandingOrderRequest,
        lease: RuntimeLease | None,
        now: datetime,
    ) -> StandingOrderPlanResult:
        reasons = _automation_block_reasons(request, lease)
        authorized = RuntimeLeaseBuilder().authorize(
            lease,
            RuntimeIntakeRequest(
                runtime_kind="cron",
                capability_id="cron.schedule.tick",
                budget_required=1,
                evidence_target=request.evidence_target,
            ),
            now=now,
        )
        if authorized.decision == "blocked":
            reasons.append(authorized.reason)
        if reasons:
            return StandingOrderPlanResult(
                decision="blocked",
                reason="standing_order_blocked",
                reasons=tuple(dict.fromkeys(reasons)),
            )

        existing = self._requests.get(request.standing_order_id)
        if existing == request:
            return StandingOrderPlanResult(
                decision="idempotent_replay",
                reason="standing_order_idempotent_replay",
                reasons=("standing_order_idempotent_replay",),
                record=self._records[request.standing_order_id],
            )
        if existing is not None:
            return StandingOrderPlanResult(
                decision="blocked",
                reason="standing_order_conflicting_replay",
                reasons=("standing_order_conflicting_replay",),
            )

        record = StandingOrderRecord(
            standing_order_id=request.standing_order_id,
            objective=request.objective,
            cron_expression=request.cron_expression,
            idempotency_key=request.idempotency_key,
            evidence_target=request.evidence_target,
            live_delivery_allowed=False,
            delivery_targets=request.delivery_targets,
        )
        self._requests[request.standing_order_id] = request
        self._records[request.standing_order_id] = record
        return StandingOrderPlanResult(
            decision="planned",
            reason="standing_order_planned_dry_run",
            reasons=("standing_order_planned_dry_run",),
            record=record,
        )


def _automation_block_reasons(
    request: StandingOrderRequest,
    lease: RuntimeLease | None,
) -> list[str]:
    reasons: list[str] = []
    approval_missing = request.approval_receipt_id is None
    if request.destructive_action_requested and approval_missing:
        reasons.append("headless_destructive_requires_approval")
    if request.live_delivery_requested and approval_missing:
        reasons.append("headless_delivery_requires_approval")
    if request.delivery_targets and approval_missing:
        reasons.append("headless_delivery_requires_approval")
    if request.live_delivery_requested and (
        lease is None or not lease.live_transport_allowed
    ):
        reasons.append("live_delivery_requires_live_transport_scope")
    return reasons


__all__ = [
    "StandingOrderPlanResult",
    "StandingOrderRecord",
    "StandingOrderRequest",
    "StandingOrderRuntime",
]
