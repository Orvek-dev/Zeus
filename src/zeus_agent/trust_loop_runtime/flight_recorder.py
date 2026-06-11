from __future__ import annotations

import json
from enum import Enum
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from .ledger import LedgerEvent, SQLiteEvidenceLedger
from .models import require_text

KIND_DECISION_RECEIPT: Final = "decision_receipt"
KIND_EXECUTION_OUTCOME: Final = "execution_outcome"
KIND_ROLLBACK_RECEIPT: Final = "rollback_receipt"
KIND_GATE_OBSERVATION: Final = "gate_observation"
KIND_LEDGER_READ: Final = "ledger_read"


class ExecutionStatus(str, Enum):
    success = "success"
    failure = "failure"
    error = "error"


class ExecutionOutcome(BaseModel):
    """What the HOST reports after executing a decided action.

    Zeus decided and recorded; the host executed. This closes the loop so the
    ledger holds failures and costs, not just optimistic decisions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    status: ExecutionStatus
    cost_actual_units: int = Field(default=0, ge=0)
    artifacts: tuple[str, ...] = ()
    notes: Optional[str] = None

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(require_text(value, "artifacts") for value in values)


class CoverageReport(BaseModel):
    """Governed-traffic share derived from gate observations.

    Every gate reports what it SAW, including actions that bypassed
    governance; the ratio of observations carrying a decision receipt is the
    coverage number that gates major versions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed: int
    governed: int
    decisions: int
    governed_pct: Optional[float] = None


class FlightRecorder:
    """Causal flight recorder over the hash-chained evidence ledger.

    Adds the four control-plane kinds (execution outcome, rollback, gate
    observation, ledger read) and the ``caused_by`` edges that turn flat
    receipts into an answerable "why did this happen" chain.
    """

    def __init__(self, ledger: SQLiteEvidenceLedger) -> None:
        self.ledger = ledger

    def record_decision(
        self,
        *,
        run_id: str,
        payload: dict[str, JsonValue],
        caused_by: tuple[str, ...] = (),
    ) -> LedgerEvent:
        return self._append(KIND_DECISION_RECEIPT, run_id, payload, caused_by)

    def record_outcome(
        self,
        *,
        run_id: str,
        outcome: ExecutionOutcome,
        caused_by: tuple[str, ...],
    ) -> LedgerEvent:
        payload: dict[str, JsonValue] = {
            "status": outcome.status.value,
            "cost_actual_units": outcome.cost_actual_units,
            "artifacts": list(outcome.artifacts),
        }
        if outcome.notes is not None:
            payload["notes"] = outcome.notes
        return self._append(KIND_EXECUTION_OUTCOME, run_id, payload, caused_by)

    def record_rollback(
        self,
        *,
        run_id: str,
        plan_id: str,
        status: ExecutionStatus,
        caused_by: tuple[str, ...],
        notes: Optional[str] = None,
    ) -> LedgerEvent:
        payload: dict[str, JsonValue] = {
            "plan_id": require_text(plan_id, "plan_id"),
            "status": status.value,
        }
        if notes is not None:
            payload["notes"] = notes
        return self._append(KIND_ROLLBACK_RECEIPT, run_id, payload, caused_by)

    def record_gate_observation(
        self,
        *,
        run_id: str,
        host: str,
        surface: str,
        capability_id: str,
        governed: bool,
        decision_receipt_record_id: Optional[str] = None,
    ) -> LedgerEvent:
        payload: dict[str, JsonValue] = {
            "host": require_text(host, "host"),
            "surface": require_text(surface, "surface"),
            "capability_id": require_text(capability_id, "capability_id"),
            "governed": governed,
        }
        caused_by: tuple[str, ...] = ()
        if decision_receipt_record_id is not None:
            payload["decision_receipt_record_id"] = decision_receipt_record_id
            caused_by = (decision_receipt_record_id,)
        return self._append(KIND_GATE_OBSERVATION, run_id, payload, caused_by)

    def record_ledger_read(
        self,
        *,
        run_id: str,
        principal_id: str,
        session_id: Optional[str],
        record_count: int,
    ) -> LedgerEvent:
        payload: dict[str, JsonValue] = {
            "principal_id": require_text(principal_id, "principal_id"),
            "record_count": record_count,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        return self._append(KIND_LEDGER_READ, run_id, payload, ())

    def why(self, record_id: str) -> tuple[dict[str, JsonValue], ...]:
        """Walk the causal chain: the record, then everything that caused it."""
        chain: list[dict[str, JsonValue]] = []
        seen: set[str] = set()
        frontier = [require_text(record_id, "record_id")]
        while frontier:
            current = frontier.pop(0)
            if current in seen:
                continue
            seen.add(current)
            record = self.ledger.record_by_id(current)
            if record is None:
                continue
            chain.append(record)
            payload = _payload_of(record)
            for parent in payload.get("caused_by", []) or []:
                if isinstance(parent, str):
                    frontier.append(parent)
        return tuple(chain)

    def coverage(self) -> CoverageReport:
        observed = 0
        governed = 0
        decisions = 0
        for record in self.ledger.records():
            kind = str(record["kind"])
            if kind == KIND_DECISION_RECEIPT:
                decisions += 1
            elif kind == KIND_GATE_OBSERVATION:
                observed += 1
                if bool(_payload_of(record).get("governed")):
                    governed += 1
        pct = round(governed / observed, 4) if observed > 0 else None
        return CoverageReport(
            observed=observed,
            governed=governed,
            decisions=decisions,
            governed_pct=pct,
        )

    def _append(
        self,
        kind: str,
        run_id: str,
        payload: dict[str, JsonValue],
        caused_by: tuple[str, ...],
    ) -> LedgerEvent:
        enriched = dict(payload)
        if caused_by:
            enriched["caused_by"] = [require_text(value, "caused_by") for value in caused_by]
        return self.ledger.append(kind=kind, run_id=run_id, payload=enriched)


def _payload_of(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}
