from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import RunState


class WorkflowExecutionStateStore:
    """Durable home for run state — so a run can suspend at an approval gate and
    resume in a different process. One row per run, the RunState serialized as
    JSON (the candidate DAG travels inside it)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save(self, run: RunState) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO workflow_runs(run_id, status, state_json, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET "
                "status = excluded.status, state_json = excluded.state_json, "
                "updated_at = excluded.updated_at",
                (run.run_id, run.status.value, run.model_dump_json(), updated_at),
            )

    def load(self, run_id: str) -> Optional[RunState]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM workflow_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RunState.model_validate_json(str(row[0]))

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS workflow_runs ("
                "run_id TEXT PRIMARY KEY, "
                "status TEXT NOT NULL, "
                "state_json TEXT NOT NULL, "
                "updated_at TEXT NOT NULL"
                ")",
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
