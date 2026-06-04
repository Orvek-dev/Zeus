from __future__ import annotations

import sqlite3
from pathlib import Path

from zeus_agent.gateway_runtime.persistence import (
    gateway_request_hash,
    is_secret_like_identifier,
    persisted_message,
    stable_hash,
)
from zeus_agent.gateway_runtime.store_sqlite import (
    initialize_gateway_schema,
    insert_audit,
    insert_session_with_idempotency,
    side_effect_flags,
)
from zeus_agent.gateway_runtime.session_types import (
    GatewayAuditSummary,
    GatewaySession,
    GatewaySessionFieldError,
    GatewaySessionIdempotencyConflict,
    GatewaySessionStoreCounts,
)


class SQLiteGatewaySessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._initialize()

    def create_or_replay_session(
        self,
        *,
        session_id: str,
        run_id: str,
        goal_contract_id: str,
        resume_token: str,
        message: str,
        idempotency_key: str,
        authority_fingerprint: str,
    ) -> GatewaySession:
        raw_message = _require_non_empty(message, "message")
        sid, rid, gid, msg, idem, authority = (
            _require_public_identifier(session_id, "session_id"),
            _require_public_identifier(run_id, "run_id"),
            _require_public_identifier(goal_contract_id, "goal_contract_id"),
            persisted_message(raw_message),
            _require_public_identifier(idempotency_key, "idempotency_key"),
            _require_non_empty(authority_fingerprint, "authority_fingerprint"),
        )
        token_hash = stable_hash(_require_non_empty(resume_token, "resume_token"))
        request_hash = gateway_request_hash(sid, rid, gid, token_hash, raw_message, authority)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id, request_hash FROM gateway_idempotency "
                "WHERE idempotency_key = ?",
                (idem,),
            ).fetchone()
            if row is not None:
                return self._replay_session(connection, row, request_hash, idem, rid, gid, msg)
            if self._session_exists(connection, sid):
                insert_audit(connection, "idempotency_conflict", "idempotency_conflict", sid, rid, gid, msg)
                connection.commit()
                raise GatewaySessionIdempotencyConflict("gateway_sessions", "session_id", sid)
            try:
                insert_session_with_idempotency(
                    connection,
                    session_id=sid,
                    run_id=rid,
                    goal_contract_id=gid,
                    resume_token_hash=token_hash,
                    authority_fingerprint_hash=authority,
                    message=msg,
                    idempotency_key=idem,
                    request_hash=request_hash,
                )
            except sqlite3.IntegrityError as error:
                insert_audit(connection, "idempotency_conflict", "idempotency_conflict", sid, rid, gid, msg)
                connection.commit()
                raise GatewaySessionIdempotencyConflict("gateway_sessions", "session_id", sid) from error
            insert_audit(connection, "session_created", "session_created", sid, rid, gid, msg)
        return GatewaySession(sid, rid, gid, msg, False)

    def resume_session(
        self,
        session_id: str,
        resume_token: str,
        message: str,
        *,
        authority_fingerprint: str,
    ) -> GatewaySession | None:
        sid = _require_non_empty(session_id, "session_id")
        msg = persisted_message(_require_non_empty(message, "message"))
        token_hash = stable_hash(_require_non_empty(resume_token, "resume_token"))
        authority = _require_non_empty(authority_fingerprint, "authority_fingerprint")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id, run_id, goal_contract_id, message, resume_token_hash, "
                "authority_fingerprint_hash FROM gateway_sessions WHERE session_id = ?",
                (sid,),
            ).fetchone()
            if row is None or row[4] != token_hash:
                insert_audit(
                    connection,
                    "resume_denied",
                    "resume_token_mismatch",
                    sid,
                    "unknown",
                    "unknown",
                    msg,
                )
                return None
            if row[5] != authority:
                insert_audit(
                    connection,
                    "resume_denied",
                    "resume_authority_mismatch",
                    row[0],
                    row[1],
                    row[2],
                    msg,
                )
                return None
            insert_audit(
                connection,
                "session_resumed",
                "resume_token_matched",
                row[0],
                row[1],
                row[2],
                msg,
            )
        return GatewaySession(row[0], row[1], row[2], row[3], False)

    def record_block(
        self,
        *,
        session_id: str,
        run_id: str,
        goal_contract_id: str,
        reason: str,
        message: str,
    ) -> None:
        with self._connect() as connection:
            insert_audit(
                connection,
                "blocked",
                _require_non_empty(reason, "reason"),
                _require_non_empty(session_id, "session_id"),
                _require_non_empty(run_id, "run_id"),
                _require_non_empty(goal_contract_id, "goal_contract_id"),
                _require_non_empty(message, "message"),
            )

    def counts(self) -> GatewaySessionStoreCounts:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT (SELECT COUNT(*) FROM gateway_sessions), "
                "(SELECT COUNT(*) FROM gateway_idempotency), "
                "(SELECT COUNT(*) FROM gateway_audit)",
            ).fetchone()
            flags = side_effect_flags(connection)
        return GatewaySessionStoreCounts(row[0], row[1], row[2], flags[0], flags[1], flags[2])

    def audit_summary(self) -> GatewayAuditSummary:
        counts = self.counts()
        return GatewayAuditSummary(
            counts.sessions,
            counts.idempotency_records,
            counts.audit_records,
            counts.handler_executed,
            counts.network_opened,
            counts.side_effects,
        )

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            initialize_gateway_schema(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _session_exists(self, connection: sqlite3.Connection, session_id: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM gateway_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row is not None

    def _replay_session(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        request_hash: str,
        idempotency_key: str,
        run_id: str,
        goal_contract_id: str,
        message: str,
    ) -> GatewaySession:
        if row[1] != request_hash:
            insert_audit(
                connection,
                "idempotency_conflict",
                "idempotency_conflict",
                row[0],
                run_id,
                goal_contract_id,
                message,
            )
            connection.commit()
            raise GatewaySessionIdempotencyConflict(
                "gateway_idempotency",
                "idempotency_key",
                idempotency_key,
            )
        session = connection.execute(
            "SELECT session_id, run_id, goal_contract_id, message "
            "FROM gateway_sessions WHERE session_id = ?",
            (row[0],),
        ).fetchone()
        insert_audit(
            connection,
            "session_replayed",
            "idempotency_replayed",
            session[0],
            session[1],
            session[2],
            message,
        )
        return GatewaySession(session[0], session[1], session[2], session[3], True)


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if text:
        return text
    raise GatewaySessionFieldError(field_name)


def _require_public_identifier(value: str, field_name: str) -> str:
    text = _require_non_empty(value, field_name)
    if is_secret_like_identifier(text):
        raise GatewaySessionFieldError(field_name)
    return text
