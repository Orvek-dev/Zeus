from __future__ import annotations

import json
from enum import Enum
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from .flight_recorder import FlightRecorder
from .models import require_text

# Payload keys that describe the governance machinery itself. An agent that can
# read its own trust thresholds can optimize against them (Goodhart), so these
# never appear in an agent-scoped view.
_AGENT_MASKED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "trust",
        "trust_score",
        "trust_threshold",
        "trust_stats",
        "policy_reason",
        "policy_internals",
        "policy_profile",
    }
)

# Whole kinds an agent never sees: ledger reads (meta-audit trail) and any
# future policy-configuration records.
_AGENT_HIDDEN_KINDS: Final[frozenset[str]] = frozenset({"ledger_read", "policy_config"})


class LedgerPrincipalKind(str, Enum):
    user = "user"
    agent = "agent"


class LedgerReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: str
    records: tuple[dict[str, JsonValue], ...] = ()
    scope: str = "none"
    read_receipt_record_id: Optional[str] = None
    taint_label: Optional[str] = None
    blocked_reason: Optional[str] = None


class GovernedLedgerReader:
    """``ledger.read`` as a governed capability, not a file handle.

    The console/user principal sees everything. An agent principal sees only
    its own session, masked of policy internals; the read itself is appended
    to the ledger (meta-audit) and the returned data is declared untrusted so
    downstream sensitive sinks re-escalate (anti-Goodhart).
    """

    def __init__(self, recorder: FlightRecorder) -> None:
        self._recorder = recorder

    def read(
        self,
        *,
        principal_kind: LedgerPrincipalKind,
        principal_id: str,
        run_id: str = "ledger.read",
        session_id: Optional[str] = None,
    ) -> LedgerReadResult:
        principal = require_text(principal_id, "principal_id")
        if principal_kind is LedgerPrincipalKind.user:
            return LedgerReadResult(
                decision="allowed",
                records=tuple(self._recorder.ledger.records()),
                scope="full",
            )
        if session_id is None or session_id.strip() == "":
            return LedgerReadResult(
                decision="blocked",
                blocked_reason="agent_read_requires_session_scope",
            )
        session = session_id.strip()
        visible = tuple(
            _mask_record(record)
            for record in self._recorder.ledger.records()
            if _agent_visible(record, session)
        )
        receipt = self._recorder.record_ledger_read(
            run_id=run_id,
            principal_id=principal,
            session_id=session,
            record_count=len(visible),
        )
        return LedgerReadResult(
            decision="allowed",
            records=visible,
            scope="session",
            read_receipt_record_id=receipt.record_id,
            taint_label="untrusted",
        )


def _agent_visible(record: dict[str, JsonValue], session_id: str) -> bool:
    if str(record["kind"]) in _AGENT_HIDDEN_KINDS:
        return False
    payload = _payload_of(record)
    return payload.get("session_id") == session_id


def _mask_record(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    payload = _payload_of(record)
    masked_payload = {
        key: value for key, value in payload.items() if key not in _AGENT_MASKED_KEYS
    }
    return {
        "record_id": record["record_id"],
        "created_at": record["created_at"],
        "kind": record["kind"],
        "run_id": record["run_id"],
        "payload": masked_payload,
    }


def _payload_of(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}
