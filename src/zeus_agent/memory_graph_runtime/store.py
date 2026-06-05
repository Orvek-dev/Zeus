from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from zeus_agent.security.credentials import redact_secret_spans

from .models import JsonObject, MemoryFact, MemoryFactStatus


class MemoryGraphStore:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.home.mkdir(parents=True, exist_ok=True)
        self.path = self.home / "memory-graph.sqlite3"
        self._ensure_schema()

    def propose_fact(
        self,
        *,
        subject: str,
        predicate: str,
        object_text: str,
        provenance_id: str,
    ) -> MemoryFact:
        raw_subject = _required_raw(subject, "subject")
        raw_predicate = _required_raw(predicate, "predicate")
        normalized_object = _required_raw(object_text, "object_text")
        raw_provenance = _required_raw(provenance_id, "provenance_id")
        normalized_subject = redact_secret_spans(raw_subject)
        normalized_predicate = redact_secret_spans(raw_predicate)
        redacted_object = redact_secret_spans(normalized_object)
        normalized_provenance = redact_secret_spans(raw_provenance)
        secret_seen = (
            normalized_subject != raw_subject
            or normalized_predicate != raw_predicate
            or redacted_object != normalized_object
            or normalized_provenance != raw_provenance
        )
        status: MemoryFactStatus = "quarantined" if secret_seen else "proposed"
        blocked_reasons = ("secret_like_content",) if status == "quarantined" else ()
        now = _utc_now()
        fact_id = _fact_id(
            subject=normalized_subject,
            predicate=normalized_predicate,
            object_text=redacted_object,
            provenance_id=normalized_provenance,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_facts(fact_id, subject, predicate, object_text, provenance_id, status, blocked_reasons_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM memory_facts WHERE fact_id = ?), ?), ?)",
                (
                    fact_id,
                    normalized_subject,
                    normalized_predicate,
                    redacted_object,
                    normalized_provenance,
                    status,
                    json.dumps(list(blocked_reasons), sort_keys=True),
                    fact_id,
                    now,
                    now,
                ),
            )
        return self.get_fact(fact_id)

    def get_fact(self, fact_id: str) -> MemoryFact:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memory_facts WHERE fact_id = ?", (fact_id,)).fetchone()
        if row is None:
            raise KeyError(fact_id)
        return _fact_from_row(row)

    def facts_for_subject(self, subject: str, *, include_deleted: bool = False) -> tuple[MemoryFact, ...]:
        sql = "SELECT * FROM memory_facts WHERE subject = ?"
        values: tuple[str, ...] = (_required(subject, "subject"),)
        if not include_deleted:
            sql = "{0} AND status != 'deleted'".format(sql)
        sql = "{0} ORDER BY created_at ASC, fact_id ASC".format(sql)
        with self._connect() as conn:
            rows = conn.execute(sql, values).fetchall()
        return tuple(_fact_from_row(row) for row in rows)

    def delete_fact(self, fact_id: str) -> MemoryFact:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE memory_facts SET object_text = ?, status = ?, blocked_reasons_json = ?, updated_at = ? WHERE fact_id = ?",
                ("[deleted]", "deleted", json.dumps(["user_deleted"], sort_keys=True), now, fact_id),
            )
        return self.get_fact(fact_id)

    def export_snapshot(self, *, include_deleted: bool = False) -> JsonObject:
        facts = self._all_facts(include_deleted=include_deleted)
        return {
            "fact_count": len([fact for fact in facts if fact.status != "deleted"]),
            "quarantined_count": len([fact for fact in facts if fact.status == "quarantined"]),
            "facts": [fact.to_payload() for fact in facts],
            "live_production_claimed": False,
        }

    def _all_facts(self, *, include_deleted: bool) -> tuple[MemoryFact, ...]:
        sql = "SELECT * FROM memory_facts"
        if not include_deleted:
            sql = "{0} WHERE status != 'deleted'".format(sql)
        sql = "{0} ORDER BY subject ASC, predicate ASC, fact_id ASC".format(sql)
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return tuple(_fact_from_row(row) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS memory_facts(fact_id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL, object_text TEXT NOT NULL, provenance_id TEXT NOT NULL, status TEXT NOT NULL, blocked_reasons_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_facts_subject ON memory_facts(subject)")


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return redact_secret_spans(normalized)


def _required_raw(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _fact_id(*, subject: str, predicate: str, object_text: str, provenance_id: str) -> str:
    payload = json.dumps(
        {
            "subject": subject,
            "predicate": predicate,
            "object_text": object_text,
            "provenance_id": provenance_id,
        },
        sort_keys=True,
    )
    return "memory-fact-{0}".format(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fact_from_row(row: sqlite3.Row) -> MemoryFact:
    blocked = tuple(str(item) for item in json.loads(str(row["blocked_reasons_json"])))
    return MemoryFact(
        fact_id=str(row["fact_id"]),
        subject=str(row["subject"]),
        predicate=str(row["predicate"]),
        object_text=str(row["object_text"]),
        provenance_id=str(row["provenance_id"]),
        status=row["status"],
        blocked_reasons=blocked,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
