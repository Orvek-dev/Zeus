from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import JsonValue

from zeus_agent.security.credentials import redact_secret_spans

from .models import ChainVerification, require_text


@dataclass(frozen=True)
class LedgerEvent:
    seq: int
    record_id: str
    entry_hash: str


class SQLiteEvidenceLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def append(
        self,
        *,
        kind: str,
        run_id: str,
        payload: dict[str, JsonValue],
    ) -> LedgerEvent:
        kind_value = require_text(kind, "kind")
        run_id_value = require_text(run_id, "run_id")
        with self._connect() as connection:
            seq = _next_seq(connection)
            prev_hash = _previous_hash(connection)
            redacted_payload = _redact_json(payload)
            payload_json = _canonical_json(redacted_payload)
            payload_hash = _sha256(payload_json)
            record_id = "trust.ev.{0:06d}".format(seq)
            created_at = datetime.now(timezone.utc).isoformat()
            entry_hash = _entry_hash(
                seq=seq,
                record_id=record_id,
                created_at=created_at,
                prev_hash=prev_hash,
                payload_hash=payload_hash,
                kind=kind_value,
                run_id=run_id_value,
            )
            connection.execute(
                "INSERT INTO trust_events("
                "seq, record_id, created_at, kind, run_id, "
                "prev_hash, payload_hash, entry_hash, payload_json"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    seq,
                    record_id,
                    created_at,
                    kind_value,
                    run_id_value,
                    prev_hash,
                    payload_hash,
                    entry_hash,
                    payload_json,
                ),
            )
        return LedgerEvent(seq=seq, record_id=record_id, entry_hash=entry_hash)

    def record_by_id(self, record_id: str) -> Optional[dict[str, JsonValue]]:
        """Point lookup via the UNIQUE index on record_id — never a full scan."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT seq, record_id, created_at, kind, run_id, "
                "prev_hash, payload_hash, entry_hash, payload_json "
                "FROM trust_events WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    def records(self) -> list[dict[str, JsonValue]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT seq, record_id, created_at, kind, run_id, "
                "prev_hash, payload_hash, entry_hash, payload_json "
                "FROM trust_events ORDER BY seq ASC",
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def verify_chain(self) -> ChainVerification:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT seq, record_id, created_at, kind, run_id, "
                "prev_hash, payload_hash, entry_hash, payload_json "
                "FROM trust_events ORDER BY seq ASC",
            ).fetchall()
        expected_prev = "GENESIS"
        for row in rows:
            record = _row_to_record(row)
            payload_json = str(record["payload_json"])
            payload_hash = _sha256(payload_json)
            if payload_hash != record["payload_hash"]:
                return ChainVerification(ok=False, reason="payload_hash_mismatch")
            expected_entry_hash = _entry_hash(
                seq=int(record["seq"]),
                record_id=str(record["record_id"]),
                created_at=str(record["created_at"]),
                prev_hash=expected_prev,
                payload_hash=payload_hash,
                kind=str(record["kind"]),
                run_id=str(record["run_id"]),
            )
            if record["prev_hash"] != expected_prev:
                return ChainVerification(ok=False, reason="prev_hash_mismatch")
            if record["entry_hash"] != expected_entry_hash:
                return ChainVerification(ok=False, reason="entry_hash_mismatch")
            expected_prev = str(record["entry_hash"])
        return ChainVerification(ok=True)

    def force_tamper_for_test(self, seq: int, payload: dict[str, JsonValue]) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE trust_events SET payload_json = ? WHERE seq = ?",
                (_canonical_json(_redact_json(payload)), seq),
            )

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS trust_events ("
                "seq INTEGER PRIMARY KEY, "
                "record_id TEXT NOT NULL UNIQUE, "
                "created_at TEXT NOT NULL, "
                "kind TEXT NOT NULL, "
                "run_id TEXT NOT NULL, "
                "prev_hash TEXT NOT NULL, "
                "payload_hash TEXT NOT NULL, "
                "entry_hash TEXT NOT NULL, "
                "payload_json TEXT NOT NULL"
                ")",
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _next_seq(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM trust_events").fetchone()
    return int(row[0])


def _previous_hash(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT entry_hash FROM trust_events ORDER BY seq DESC LIMIT 1",
    ).fetchone()
    if row is None:
        return "GENESIS"
    return str(row[0])


def _row_to_record(row: sqlite3.Row | tuple[JsonValue, ...]) -> dict[str, JsonValue]:
    return {
        "seq": row[0],
        "record_id": row[1],
        "created_at": row[2],
        "kind": row[3],
        "run_id": row[4],
        "prev_hash": row[5],
        "payload_hash": row[6],
        "entry_hash": row[7],
        "payload_json": row[8],
    }


def _redact_json(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact_secret_spans(value)
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_json(item) for key, item in value.items()}
    return value


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _entry_hash(
    *,
    seq: int,
    record_id: str,
    created_at: str,
    prev_hash: str,
    payload_hash: str,
    kind: str,
    run_id: str,
) -> str:
    material = "|".join(
        (
            str(seq),
            record_id,
            created_at,
            prev_hash,
            payload_hash,
            kind,
            run_id,
        ),
    )
    return _sha256(material)
