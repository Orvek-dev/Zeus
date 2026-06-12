from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import JsonValue

from .state_store import ReplayRow, SQLiteControlPlaneStore


@dataclass(frozen=True)
class ReplayAuthorization:
    token_id: str
    host: str
    session_id: str
    capability_id: str
    payload_hash: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None


class ReplayAuthorizationStore(Protocol):
    def add(self, authorization: ReplayAuthorization) -> None: ...

    def consume(
        self,
        *,
        host: str,
        session_id: str,
        capability_id: str,
        payload_hash: str,
        now: datetime,
    ) -> ReplayAuthorization | None: ...


class SQLiteReplayAuthorizationStore:
    def __init__(self, store: SQLiteControlPlaneStore) -> None:
        self._store = store

    def add(self, authorization: ReplayAuthorization) -> None:
        self._store.replay_add(
            token_id=authorization.token_id,
            host=authorization.host,
            session_id=authorization.session_id,
            capability_id=authorization.capability_id,
            payload_hash=authorization.payload_hash,
            created_at=authorization.created_at.isoformat(),
            expires_at=authorization.expires_at.isoformat(),
            consumed_at=(
                authorization.consumed_at.isoformat()
                if authorization.consumed_at is not None
                else ""
            ),
        )

    def consume(
        self,
        *,
        host: str,
        session_id: str,
        capability_id: str,
        payload_hash: str,
        now: datetime,
    ) -> ReplayAuthorization | None:
        row = self._store.replay_consume(
            host=host,
            session_id=session_id,
            capability_id=capability_id,
            payload_hash=payload_hash,
            now_iso=now.isoformat(),
        )
        return _row_to_authorization(row) if row is not None else None


def replay_payload_hash(payload: dict[str, JsonValue]) -> str:
    material = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _row_to_authorization(row: ReplayRow) -> ReplayAuthorization:
    (
        token_id,
        host,
        session_id,
        capability_id,
        payload_hash,
        created_at,
        expires_at,
        consumed_at,
    ) = row
    return ReplayAuthorization(
        token_id=token_id,
        host=host,
        session_id=session_id,
        capability_id=capability_id,
        payload_hash=payload_hash,
        created_at=datetime.fromisoformat(created_at),
        expires_at=datetime.fromisoformat(expires_at),
        consumed_at=datetime.fromisoformat(consumed_at) if consumed_at else None,
    )
