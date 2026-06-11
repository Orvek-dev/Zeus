from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

QueueRow = tuple[str, str, str, str, str, str]
_QUEUE_COLUMNS = (
    "parked_action_id, action_id, action_json, status, created_at, expires_at"
)


class SQLiteControlPlaneStore:
    """Shared durable state for gate processes (GAP-1).

    A hook process lives for one decision, and the proxy daemon is a separate
    process again — so budget counters, the approval queue, and the decision
    sequence must live here, not in engine memory, or pre-call enforcement is
    defeated the moment the process exits. Rows are plain columns/JSON text;
    model (de)serialization stays with the callers to keep this module
    dependency-free.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ---------------------------------------------------------------- budgets
    def set_budget_limit(self, scope: str, scope_id: str, max_units: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO budget_limits(scope, scope_id, max_units) VALUES (?, ?, ?) "
                "ON CONFLICT(scope, scope_id) DO UPDATE SET max_units = excluded.max_units",
                (scope, scope_id, max_units),
            )

    def budget_limit(self, scope: str, scope_id: str) -> Optional[int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT max_units FROM budget_limits WHERE scope = ? AND scope_id = ?",
                (scope, scope_id),
            ).fetchone()
        return int(row[0]) if row is not None else None

    def add_budget_spend(self, scope: str, scope_id: str, units: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO budget_spent(scope, scope_id, spent) VALUES (?, ?, ?) "
                "ON CONFLICT(scope, scope_id) DO UPDATE SET spent = spent + excluded.spent",
                (scope, scope_id, units),
            )

    def budget_spent(self, scope: str, scope_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT spent FROM budget_spent WHERE scope = ? AND scope_id = ?",
                (scope, scope_id),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def budget_rows(self) -> list[tuple[str, str, int, int]]:
        """(scope, scope_id, max_units, spent) for every configured limit."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT l.scope, l.scope_id, l.max_units, COALESCE(s.spent, 0) "
                "FROM budget_limits l LEFT JOIN budget_spent s "
                "ON s.scope = l.scope AND s.scope_id = l.scope_id "
                "ORDER BY l.scope, l.scope_id",
            ).fetchall()
        return [(str(r[0]), str(r[1]), int(r[2]), int(r[3])) for r in rows]

    # -------------------------------------------------------------- envelopes
    def envelope_save(self, objective_id: str, envelope_json: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO envelopes(objective_id, envelope_json) VALUES (?, ?) "
                "ON CONFLICT(objective_id) DO UPDATE SET envelope_json = excluded.envelope_json",
                (objective_id, envelope_json),
            )

    def envelope_get(self, objective_id: str) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT envelope_json FROM envelopes WHERE objective_id = ?",
                (objective_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    # ----------------------------------------------------- capability records
    def capability_save(self, capability_id: str, record_json: str) -> None:
        """Durable registry rows for gate-imported capabilities (MCP tools,
        quarantined skills) — quarantine status must survive process exit."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO capability_records(capability_id, record_json) VALUES (?, ?) "
                "ON CONFLICT(capability_id) DO UPDATE SET record_json = excluded.record_json",
                (capability_id, record_json),
            )

    def capability_get(self, capability_id: str) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM capability_records WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def capability_all(self) -> list[tuple[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT capability_id, record_json FROM capability_records "
                "ORDER BY capability_id",
            ).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]

    # --------------------------------------------------------------------- kv
    def kv_set(self, name: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO kv(name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
                (name, value),
            )

    def kv_get(self, name: str) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM kv WHERE name = ?", (name,)).fetchone()
        return str(row[0]) if row is not None else None

    # ---------------------------------------------------------------- novelty
    def novelty_first_seen(self, kind: str, value: str) -> bool:
        """True exactly once per (kind, value) — the sighting is learned."""
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO novelty_seen(kind, value) VALUES (?, ?)",
                (kind, value),
            )
        return cursor.rowcount == 1

    # --------------------------------------------------------------- counters
    def next_counter(self, name: str) -> int:
        """Atomic cross-process increment; first call returns 1."""
        with self._connect() as connection:
            row = connection.execute(
                "INSERT INTO counters(name, value) VALUES (?, 1) "
                "ON CONFLICT(name) DO UPDATE SET value = value + 1 "
                "RETURNING value",
                (name,),
            ).fetchone()
        return int(row[0])

    # ------------------------------------------------------------------ queue
    def queue_park(
        self,
        *,
        parked_action_id: str,
        action_id: str,
        action_json: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        """Supersede any pending park for the same action, then insert — one
        transaction, so two gate processes cannot both hold the active park."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE parked_actions SET status = 'superseded' "
                "WHERE action_id = ? AND status = 'pending'",
                (action_id,),
            )
            connection.execute(
                "INSERT INTO parked_actions("
                + _QUEUE_COLUMNS
                + ") VALUES (?, ?, ?, 'pending', ?, ?)",
                (parked_action_id, action_id, action_json, created_at, expires_at),
            )

    def queue_row(self, parked_action_id: str) -> Optional[QueueRow]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT " + _QUEUE_COLUMNS + " FROM parked_actions WHERE parked_action_id = ?",
                (parked_action_id,),
            ).fetchone()
        return tuple(row) if row is not None else None

    def queue_expire_due(self, now_iso: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE parked_actions SET status = 'expired' "
                "WHERE status = 'pending' AND expires_at <= ?",
                (now_iso,),
            )

    def queue_rows(self, *, status: Optional[str] = None) -> list[QueueRow]:
        query = "SELECT " + _QUEUE_COLUMNS + " FROM parked_actions"
        params: tuple[str, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at ASC, parked_action_id ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [tuple(row) for row in rows]

    def queue_set_status(self, parked_action_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE parked_actions SET status = ? WHERE parked_action_id = ?",
                (status, parked_action_id),
            )

    # ----------------------------------------------------------------- schema
    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS budget_limits ("
                "scope TEXT NOT NULL, scope_id TEXT NOT NULL, max_units INTEGER NOT NULL, "
                "PRIMARY KEY (scope, scope_id))",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS budget_spent ("
                "scope TEXT NOT NULL, scope_id TEXT NOT NULL, spent INTEGER NOT NULL, "
                "PRIMARY KEY (scope, scope_id))",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS counters ("
                "name TEXT PRIMARY KEY, value INTEGER NOT NULL)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                "name TEXT PRIMARY KEY, value TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS capability_records ("
                "capability_id TEXT PRIMARY KEY, record_json TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS envelopes ("
                "objective_id TEXT PRIMARY KEY, envelope_json TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS novelty_seen ("
                "kind TEXT NOT NULL, value TEXT NOT NULL, "
                "PRIMARY KEY (kind, value))",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS parked_actions ("
                "parked_action_id TEXT PRIMARY KEY, "
                "action_id TEXT NOT NULL, "
                "action_json TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "expires_at TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_parked_actions_status "
                "ON parked_actions(status)",
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_parked_actions_action "
                "ON parked_actions(action_id, status)",
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
