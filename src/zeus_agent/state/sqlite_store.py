from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from zeus_agent.kernel.evidence import MnemeEvidenceRecord
from zeus_agent.state.idempotency import SQLiteValue, confirm_existing_row


class StateCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sessions: int
    model_turns: int
    tool_calls: int
    evidence_records: int
    acceptance_links: int
    artifacts: int
    connectors: int
    workflows: int
    ops_events: int
    audit_events: int


class SQLiteStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._init_schema(connection)

    def create_session(self, session_id: str, run_id: str, goal_contract_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO session_state_sessions(session_id, run_id, goal_contract_id) "
                "VALUES (?, ?, ?)",
                (session_id, run_id, goal_contract_id),
            )

    def add_model_turn(self, turn_id: str, session_id: str, role: str, content: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO session_state_model_turns(turn_id, session_id, role, content) "
                "VALUES (?, ?, ?, ?)",
                (turn_id, session_id, role, content),
            )

    def add_tool_call(
        self,
        tool_call_id: str,
        turn_id: str,
        capability_id: str,
        payload: dict[str, str],
        broker_decision: str,
        handler_executed: bool,
        evidence_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO session_state_tool_calls("
                "tool_call_id, turn_id, capability_id, payload_json, "
                "broker_decision, handler_executed, evidence_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    tool_call_id,
                    turn_id,
                    capability_id,
                    json.dumps(payload, sort_keys=True),
                    broker_decision,
                    int(handler_executed),
                    evidence_id,
                ),
            )

    def add_evidence(self, evidence_id: str, record: MnemeEvidenceRecord) -> None:
        columns = (
            "evidence_id",
            "run_id",
            "goal_contract_id",
            "criterion_id",
            "evidence_type",
            "summary",
            "status",
            "capability_id",
        )
        values: tuple[SQLiteValue, ...] = (
            evidence_id,
            record.run_id,
            record.goal_contract_id,
            record.criterion_id,
            record.evidence_type,
            record.summary,
            record.status.value,
            record.capability_id,
        )
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO evidence_state_records("
                    "evidence_id, run_id, goal_contract_id, criterion_id, "
                    "evidence_type, summary, status, capability_id"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            except sqlite3.IntegrityError as exc:
                confirm_existing_row(
                    connection,
                    table_name="evidence_state_records",
                    columns=columns,
                    key_column="evidence_id",
                    key_value=evidence_id,
                    values=values,
                    cause=exc,
                )

    def add_acceptance_link(self, criterion_id: str, evidence_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO evidence_state_acceptance_links(criterion_id, evidence_id, status) "
                "VALUES (?, ?, ?)",
                (criterion_id, evidence_id, status),
            )

    def add_audit_event(self, event_id: str, summary: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_log_events(event_id, summary) VALUES (?, ?)",
                (event_id, summary),
            )

    def counts(self) -> StateCounts:
        return StateCounts(
            sessions=self._count("session_state_sessions"),
            model_turns=self._count("session_state_model_turns"),
            tool_calls=self._count("session_state_tool_calls"),
            evidence_records=self._count("evidence_state_records"),
            acceptance_links=self._count("evidence_state_acceptance_links"),
            artifacts=self._count("artifact_state_artifacts"),
            connectors=self._count("connector_state_connectors"),
            workflows=self._count("workflow_state_workflows"),
            ops_events=self._count("ops_telemetry_events"),
            audit_events=self._count("audit_log_events"),
        )

    def _count(self, table_name: str) -> int:
        with self._connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _init_schema(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA user_version=2")
        for statement in _SCHEMA:
            connection.execute(statement)


_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS session_state_sessions("
    "session_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, goal_contract_id TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS session_state_model_turns("
    "turn_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES session_state_sessions(session_id), "
    "role TEXT NOT NULL, content TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS session_state_tool_calls("
    "tool_call_id TEXT PRIMARY KEY, turn_id TEXT NOT NULL REFERENCES session_state_model_turns(turn_id), "
    "capability_id TEXT NOT NULL, payload_json TEXT NOT NULL, broker_decision TEXT NOT NULL, "
    "handler_executed INTEGER NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id))",
    "CREATE TABLE IF NOT EXISTS evidence_state_records("
    "evidence_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, goal_contract_id TEXT NOT NULL, "
    "criterion_id TEXT NOT NULL, evidence_type TEXT NOT NULL, summary TEXT NOT NULL, "
    "status TEXT NOT NULL, capability_id TEXT)",
    "CREATE TABLE IF NOT EXISTS evidence_state_acceptance_links("
    "criterion_id TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "status TEXT NOT NULL, PRIMARY KEY(criterion_id, evidence_id))",
    "CREATE TABLE IF NOT EXISTS artifact_state_artifacts("
    "artifact_id TEXT PRIMARY KEY, path TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS connector_state_connectors("
    "connector_id TEXT PRIMARY KEY, health TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS workflow_state_workflows("
    "workflow_id TEXT PRIMARY KEY, status TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS ops_telemetry_events("
    "event_id TEXT PRIMARY KEY, summary TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS audit_log_events("
    "event_id TEXT PRIMARY KEY, summary TEXT NOT NULL)",
]
