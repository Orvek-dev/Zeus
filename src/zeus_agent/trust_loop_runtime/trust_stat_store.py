from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class SQLiteTrustStatStore:
    """Persistent home for earned-trust counts (success/failure per capability).

    The earned-autonomy flywheel leaks if trust lives only in memory: a restart
    resets every capability to untrusted. This SQLite table is the durable
    sibling of the append-only evidence ledger — trust counts survive restarts
    and can be rebuilt by folding evidence (see WorkflowExecutionRuntime in M1,
    which is the caller that records per-node success/failure).

    Stores raw ints (not TrustStat) so it never imports trust_ledger — keeping
    the dependency one-directional and cycle-free.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get(self, capability_id: str) -> Optional[tuple[int, int]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT success_count, failure_count FROM trust_stats WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()
        if row is None:
            return None
        return int(row[0]), int(row[1])

    def upsert(self, capability_id: str, *, success_count: int, failure_count: int) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO trust_stats(capability_id, success_count, failure_count, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(capability_id) DO UPDATE SET "
                "success_count = excluded.success_count, "
                "failure_count = excluded.failure_count, "
                "updated_at = excluded.updated_at",
                (capability_id, success_count, failure_count, updated_at),
            )

    def all(self) -> dict[str, tuple[int, int]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT capability_id, success_count, failure_count FROM trust_stats",
            ).fetchall()
        return {str(row[0]): (int(row[1]), int(row[2])) for row in rows}

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS trust_stats ("
                "capability_id TEXT PRIMARY KEY, "
                "success_count INTEGER NOT NULL, "
                "failure_count INTEGER NOT NULL, "
                "updated_at TEXT NOT NULL"
                ")",
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
