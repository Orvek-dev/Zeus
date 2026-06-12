from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, field_validator

from .models import TrustLoopAction, require_text
from .state_store import QueueRow, SQLiteControlPlaneStore

ParkedActionStatus = Literal["pending", "approved", "rejected", "expired", "superseded"]


class ParkedAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    parked_action_id: str
    action: TrustLoopAction
    status: ParkedActionStatus = "pending"
    created_at: datetime
    expires_at: datetime
    host: str = ""
    session_id: str = ""
    payload_hash: str = ""

    @field_validator("parked_action_id")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value, "parked_action_id")


class ApprovalQueue:
    def __init__(self) -> None:
        self._actions: dict[str, ParkedAction] = {}
        self._active_by_action_id: dict[str, str] = {}

    def park(
        self,
        action: TrustLoopAction,
        *,
        ttl_seconds: int = 600,
        host: str = "",
        session_id: str = "",
        payload_hash: str = "",
    ) -> ParkedAction:
        created_at = datetime.now(timezone.utc)
        active_id = self._active_by_action_id.get(action.action_id)
        if active_id is not None:
            current = self._actions[active_id]
            self._actions[active_id] = current.model_copy(update={"status": "superseded"})
        parked = ParkedAction(
            parked_action_id=_parked_action_id(action, len(self._actions) + 1),
            action=action,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
            host=host,
            session_id=session_id,
            payload_hash=payload_hash,
        )
        self._actions[parked.parked_action_id] = parked
        self._active_by_action_id[action.action_id] = parked.parked_action_id
        return parked

    def get(self, parked_action_id: str) -> ParkedAction:
        return self._actions[parked_action_id]

    def pending(self, *, now: datetime) -> tuple[ParkedAction, ...]:
        refreshed = []
        for parked in self._actions.values():
            refreshed.append(_expire_if_needed(parked, now=now))
        self._actions = {parked.parked_action_id: parked for parked in refreshed}
        return tuple(parked for parked in refreshed if parked.status == "pending")


class SQLiteApprovalQueue(ApprovalQueue):
    """Approval queue over the shared control-plane store (GAP-1).

    Each gate invocation is its own process; an ASK parked by one process must
    be visible to the console and to every later process, and a park must
    survive until a human resolves it or its TTL expires.
    """

    def __init__(self, store: SQLiteControlPlaneStore) -> None:
        self._store = store

    def park(
        self,
        action: TrustLoopAction,
        *,
        ttl_seconds: int = 600,
        host: str = "",
        session_id: str = "",
        payload_hash: str = "",
    ) -> ParkedAction:
        created_at = datetime.now(timezone.utc)
        parked = ParkedAction(
            parked_action_id=_parked_action_id(
                action, self._store.next_counter("parked_action_seq")
            ),
            action=action,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
            host=host,
            session_id=session_id,
            payload_hash=payload_hash,
        )
        self._store.queue_park(
            parked_action_id=parked.parked_action_id,
            action_id=action.action_id,
            action_json=action.model_dump_json(),
            created_at=parked.created_at.isoformat(),
            expires_at=parked.expires_at.isoformat(),
            dedup_key=_dedup_key(action),
            host=host,
            session_id=session_id,
            payload_hash=payload_hash,
        )
        return parked

    def get(self, parked_action_id: str) -> ParkedAction:
        row = self._store.queue_row(parked_action_id)
        if row is None:
            raise KeyError(parked_action_id)
        return _row_to_parked(row)

    def pending(self, *, now: datetime) -> tuple[ParkedAction, ...]:
        self._store.queue_expire_due(now.isoformat())
        return tuple(_row_to_parked(row) for row in self._store.queue_rows(status="pending"))

    def resolve(
        self, parked_action_id: str, *, approved: bool, now: datetime | None = None
    ) -> ParkedAction:
        """Operator verdict on a parked ASK (async surfaces resolve here).

        TTL is fail-closed HERE, not only in pending(): a park past its expiry
        can never become approved, even if nothing swept it to expired yet —
        an approval that raced the deadline must not authorize anything."""
        current = self.get(parked_action_id)
        timestamp = now if now is not None else datetime.now(timezone.utc)
        expired = _expire_if_needed(current, now=timestamp)
        if expired.status != current.status:
            self._store.queue_set_status(parked_action_id, "expired")
            return expired
        if current.status != "pending":
            return current
        status: ParkedActionStatus = "approved" if approved else "rejected"
        self._store.queue_set_status(parked_action_id, status)
        return current.model_copy(update={"status": status})


def _dedup_key(action: TrustLoopAction) -> str:
    """Stable identity of a parkable request: the same capability, run, and
    payload retried by a host must collapse to ONE pending row (D4)."""
    material = json.dumps(
        {"c": action.capability_id, "r": action.run_id, "p": action.payload},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _row_to_parked(row: QueueRow) -> ParkedAction:
    (
        parked_action_id,
        _action_id,
        action_json,
        status,
        created_at,
        expires_at,
        host,
        session_id,
        payload_hash,
    ) = row
    return ParkedAction(
        parked_action_id=parked_action_id,
        action=TrustLoopAction.model_validate_json(action_json),
        status=cast(ParkedActionStatus, status),
        created_at=datetime.fromisoformat(created_at),
        expires_at=datetime.fromisoformat(expires_at),
        host=host,
        session_id=session_id,
        payload_hash=payload_hash,
    )


def _expire_if_needed(parked: ParkedAction, *, now: datetime) -> ParkedAction:
    if parked.status != "pending":
        return parked
    if parked.expires_at <= now:
        return parked.model_copy(update={"status": "expired"})
    return parked


def _parked_action_id(action: TrustLoopAction, seq: int) -> str:
    return "trust.parked.{0}.{1}".format(action.action_id.replace(".", "_"), seq)
