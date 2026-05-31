"""SQLite state store for sessions, messages, evidence, and artifacts.

JSON/JSONL files remain the append-only audit trail. This store is the queryable
local index inspired by Hermes' session database: fast search and resumability
without sending anything off-machine.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from zeus_agent.paths import ensure_private_dir, ensure_private_file, init_home, state_db_path
from zeus_agent.schemas.agent import AgentMessage


SCHEMA_VERSION = 1


class StateStore:
    def __init__(self, home: Path | None = None) -> None:
        paths = init_home(home)
        self.home = paths["home"]
        self.path = state_db_path(self.home)
        ensure_private_file(self.path)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_session(self, session_id: str, *, run_id: str | None, title: str, status: str = "active") -> None:
        now = _now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, run_id, title, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                  run_id=excluded.run_id,
                  title=excluded.title,
                  status=excluded.status,
                  updated_at=excluded.updated_at
                """,
                (session_id, run_id, title, status, now, now),
            )

    def append_message(self, message: AgentMessage) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO messages(message_id, session_id, run_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.session_id,
                    message.run_id,
                    message.role,
                    message.content,
                    message.created_at.isoformat(),
                ),
            )
            _try_fts_insert(conn, message.session_id, message.role, message.content)

    def index_evidence(
        self,
        run_id: str,
        evidence_id: str,
        evidence_type: str,
        summary: str,
        *,
        passed: bool | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_index(
                  evidence_id, run_id, evidence_type, summary, passed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (evidence_id, run_id, evidence_type, summary, _bool_to_int(passed), _now()),
            )

    def record_artifact(
        self,
        run_id: str,
        artifact_path: str,
        artifact_type: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts(run_id, artifact_path, artifact_type, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, artifact_path, artifact_type, json.dumps(metadata or {}, ensure_ascii=False), _now()),
            )

    def search_messages(self, query: str, *, limit: int = 20) -> list[dict[str, object]]:
        query = query.strip()
        if not query:
            return []
        with self.connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT session_id, role, content
                    FROM messages_fts
                    WHERE messages_fts MATCH ?
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """
                    SELECT session_id, role, content
                    FROM messages
                    WHERE content LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def recent_artifacts(self, *, limit: int = 20) -> list[dict[str, object]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, artifact_path, artifact_type, metadata_json, created_at
                FROM artifacts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        ensure_private_dir(self.path.parent)
        with self.connect() as conn:
            conn.execute("PRAGMA user_version = 1")
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.DatabaseError:
                conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  session_id TEXT PRIMARY KEY,
                  run_id TEXT,
                  title TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                  message_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  run_id TEXT,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_index (
                  evidence_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  evidence_type TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  passed INTEGER,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                  artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT NOT NULL,
                  artifact_path TEXT NOT NULL,
                  artifact_type TEXT NOT NULL,
                  metadata_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                    USING fts5(session_id, role, content)
                    """
                )
            except sqlite3.OperationalError:
                pass


def _try_fts_insert(conn: sqlite3.Connection, session_id: str, role: str, content: str) -> None:
    try:
        conn.execute(
            "INSERT INTO messages_fts(session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
    except sqlite3.OperationalError:
        pass


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _now() -> str:
    return datetime.now(UTC).isoformat()

