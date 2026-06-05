from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from zeus_agent.security.credentials import redact_secret_spans


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    profile: str
    provider_id: str
    title: str
    created_at: str
    updated_at: str

    def to_payload(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "profile": self.profile,
            "provider_id": self.provider_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ChatMessage:
    session_id: str
    role: str
    content: str
    created_at: str

    def to_payload(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }


class SessionStore:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.home.mkdir(parents=True, exist_ok=True)
        self.path = self.home / "sessions.sqlite3"
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, profile TEXT NOT NULL, provider_id TEXT NOT NULL, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessions(session_id))")
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(session_id, role, content)",
                )
            except sqlite3.OperationalError:
                conn.execute("CREATE TABLE IF NOT EXISTS message_fts (session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL)")

    def ensure_session(
        self,
        *,
        session_id: str,
        profile: str,
        provider_id: str,
        title: str,
    ) -> SessionRecord:
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO sessions(session_id, profile, provider_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, redact_secret_spans(profile), redact_secret_spans(provider_id), redact_secret_spans(title), now, now),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (now, session_id),
                )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> SessionRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return _session_from_row(row)

    def append_message(self, *, session_id: str, role: str, content: str) -> ChatMessage:
        normalized_role = role.strip()
        if normalized_role not in {"system", "user", "assistant", "tool"}:
            raise ValueError("unsupported_role")
        now = _utc_now()
        redacted_content = redact_secret_spans(content)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, normalized_role, redacted_content, now),
            )
            conn.execute(
                "INSERT INTO message_fts(session_id, role, content) VALUES (?, ?, ?)",
                (session_id, normalized_role, redacted_content),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
        return ChatMessage(
            session_id=session_id,
            role=normalized_role,
            content=redacted_content,
            created_at=now,
        )

    def messages(self, session_id: str) -> tuple[ChatMessage, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return tuple(_message_from_row(row) for row in rows)

    def list_sessions(self) -> tuple[SessionRecord, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC, session_id ASC",
            ).fetchall()
        return tuple(_session_from_row(row) for row in rows)

    def search(self, query: str) -> tuple[ChatMessage, ...]:
        normalized = redact_secret_spans(query.strip())
        if normalized == "":
            return ()
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT m.session_id, m.role, m.content, m.created_at FROM messages m JOIN message_fts f ON f.session_id = m.session_id AND f.role = m.role AND f.content = m.content WHERE message_fts MATCH ? ORDER BY m.id DESC",
                    (normalized,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    "SELECT session_id, role, content, created_at FROM messages WHERE content LIKE ? ORDER BY id DESC",
                    (f"%{normalized}%",),
                ).fetchall()
        return tuple(_message_from_row(row) for row in rows)

    def export_session(self, session_id: str) -> dict[str, object]:
        return {
            "session": self.get_session(session_id).to_payload(),
            "messages": [message.to_payload() for message in self.messages(session_id)],
            "raw_secret_exported": False,
        }

    def import_session(self, payload: dict[str, object]) -> SessionRecord:
        session_payload = payload.get("session")
        messages_payload = payload.get("messages", [])
        if not isinstance(session_payload, dict):
            raise ValueError("missing_session")
        session = self.ensure_session(
            session_id=str(session_payload["session_id"]),
            profile=str(session_payload.get("profile", "chat")),
            provider_id=str(session_payload.get("provider_id", "fake")),
            title=str(session_payload.get("title", "Imported Session")),
        )
        if isinstance(messages_payload, Iterable):
            for item in messages_payload:
                if isinstance(item, dict):
                    self.append_message(
                        session_id=session.session_id,
                        role=str(item.get("role", "user")),
                        content=str(item.get("content", "")),
                    )
        return session

    def export_json(self, session_id: str) -> str:
        return json.dumps(self.export_session(session_id), ensure_ascii=False, sort_keys=True)


def _session_from_row(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        session_id=str(row["session_id"]),
        profile=str(row["profile"]),
        provider_id=str(row["provider_id"]),
        title=str(row["title"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _message_from_row(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        session_id=str(row["session_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        created_at=str(row["created_at"]),
    )
