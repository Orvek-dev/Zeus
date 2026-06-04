from __future__ import annotations

from dataclasses import dataclass

from zeus_agent.state.idempotency import IdempotencyConflictError


@dataclass(frozen=True, slots=True)
class GatewaySession:
    session_id: str
    run_id: str
    goal_contract_id: str
    message: str
    idempotency_replay_stable: bool
    handler_executed: bool = False
    network_opened: bool = False
    side_effects: bool = False


@dataclass(frozen=True, slots=True)
class GatewaySessionStoreCounts:
    sessions: int
    idempotency_records: int
    audit_records: int
    handler_executed: bool
    network_opened: bool
    side_effects: bool


@dataclass(frozen=True, slots=True)
class GatewayAuditSummary:
    sessions: int
    idempotency_records: int
    audit_records: int
    handler_executed: bool
    network_opened: bool
    side_effects: bool


@dataclass(frozen=True, slots=True)
class GatewaySessionFieldError(RuntimeError):
    field_name: str

    def __str__(self) -> str:
        return "{0} field is invalid".format(self.field_name)


class GatewaySessionIdempotencyConflict(IdempotencyConflictError):
    @property
    def reason(self) -> str:
        return "idempotency_conflict"
