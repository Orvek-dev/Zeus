from __future__ import annotations

import sqlite3

from zeus_agent.gateway_runtime.persistence import persisted_audit_identity, persisted_message


def initialize_gateway_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        "CREATE TABLE IF NOT EXISTS gateway_sessions(session_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, goal_contract_id TEXT NOT NULL, resume_token_hash TEXT NOT NULL, authority_fingerprint_hash TEXT NOT NULL, message TEXT NOT NULL, handler_executed INTEGER NOT NULL, network_opened INTEGER NOT NULL, side_effects INTEGER NOT NULL);"
        "CREATE TABLE IF NOT EXISTS gateway_idempotency(idempotency_key TEXT PRIMARY KEY, session_id TEXT NOT NULL, request_hash TEXT NOT NULL, FOREIGN KEY (session_id) REFERENCES gateway_sessions(session_id));"
        "CREATE TABLE IF NOT EXISTS gateway_audit(audit_id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, reason TEXT NOT NULL, session_id TEXT NOT NULL, run_id TEXT NOT NULL, goal_contract_id TEXT NOT NULL, message TEXT NOT NULL, handler_executed INTEGER NOT NULL, network_opened INTEGER NOT NULL, side_effects INTEGER NOT NULL);",
    )
    _ensure_authority_column(connection)


def insert_audit(
    connection: sqlite3.Connection,
    event: str,
    reason: str,
    session_id: str,
    run_id: str,
    goal_contract_id: str,
    message: str,
) -> None:
    connection.execute(
        "INSERT INTO gateway_audit(event, reason, session_id, run_id, goal_contract_id, "
        "message, handler_executed, network_opened, side_effects) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)",
        (
            event,
            reason,
            persisted_audit_identity(session_id),
            persisted_audit_identity(run_id),
            persisted_audit_identity(goal_contract_id),
            persisted_message(message),
        ),
    )


def insert_session_with_idempotency(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    run_id: str,
    goal_contract_id: str,
    resume_token_hash: str,
    authority_fingerprint_hash: str,
    message: str,
    idempotency_key: str,
    request_hash: str,
) -> None:
    connection.execute("SAVEPOINT gateway_create_session")
    try:
        connection.execute(
            "INSERT INTO gateway_sessions(session_id, run_id, goal_contract_id, "
            "resume_token_hash, authority_fingerprint_hash, message, handler_executed, "
            "network_opened, side_effects) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)",
            (session_id, run_id, goal_contract_id, resume_token_hash, authority_fingerprint_hash, message),
        )
        connection.execute(
            "INSERT INTO gateway_idempotency(idempotency_key, session_id, request_hash) VALUES (?, ?, ?)",
            (idempotency_key, session_id, request_hash),
        )
    except sqlite3.IntegrityError:
        connection.execute("ROLLBACK TO SAVEPOINT gateway_create_session")
        connection.execute("RELEASE SAVEPOINT gateway_create_session")
        raise
    connection.execute("RELEASE SAVEPOINT gateway_create_session")


def side_effect_flags(connection: sqlite3.Connection) -> tuple[bool, bool, bool]:
    row = connection.execute(
        "SELECT COALESCE(MAX(handler_executed), 0), COALESCE(MAX(network_opened), 0), "
        "COALESCE(MAX(side_effects), 0) FROM ("
        "SELECT handler_executed, network_opened, side_effects FROM gateway_sessions "
        "UNION ALL SELECT handler_executed, network_opened, side_effects FROM gateway_audit)",
    ).fetchone()
    return bool(row[0]), bool(row[1]), bool(row[2])


def _ensure_authority_column(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(gateway_sessions)").fetchall()}
    if "authority_fingerprint_hash" in columns:
        return
    connection.execute(
        "ALTER TABLE gateway_sessions ADD COLUMN authority_fingerprint_hash "
        "TEXT NOT NULL DEFAULT 'sha256:legacy-authority'",
    )
