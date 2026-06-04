from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final

import pytest
from pydantic import JsonValue

from zeus_agent.gateway_runtime.api import GatewayApiRuntime
from zeus_agent.gateway_runtime.models import GatewaySessionCreateRequest, GatewaySessionResumeRequest
from zeus_agent.gateway_runtime.security import GatewaySecurityRequestContext
from zeus_agent.gateway_runtime.session_store import (
    GatewaySessionIdempotencyConflict,
    SQLiteGatewaySessionStore,
)

AUTH_A: Final = "g006-http-auth-token-a"
AUTH_B: Final = "g006-http-auth-token-b"
RESUME_TOKEN: Final = "g006-http-resume-token"
SECRET_MESSAGE: Final = "use sk-g006raw Bearer g006bearer token=g006token"
JsonPayload = dict[str, JsonValue]


def test_store_redacts_secret_like_messages_before_sqlite_persistence(tmp_path: Path) -> None:
    # Given: a store receives secret-shaped message text across session and audit inserts.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)

    # When: create, resume, and block events persist the message.
    store.create_or_replay_session(
        session_id="session-secret",
        run_id="run-secret",
        goal_contract_id="goal-secret",
        resume_token=RESUME_TOKEN,
        message=SECRET_MESSAGE,
        idempotency_key="idem-secret",
        authority_fingerprint="sha256:auth-a",
    )
    store.resume_session(
        "session-secret",
        RESUME_TOKEN,
        SECRET_MESSAGE,
        authority_fingerprint="sha256:auth-a",
    )
    store.record_block(
        session_id="blocked-secret",
        run_id="run-secret",
        goal_contract_id="goal-secret",
        reason="malformed_request",
        message=SECRET_MESSAGE,
    )

    # Then: raw SQLite rows contain only persistence-safe redacted text.
    stored_text = _sqlite_text(db_path)
    assert "sk-" not in stored_text
    assert "Bearer" not in stored_text
    assert "token=" not in stored_text
    assert "g006raw" not in stored_text
    assert "g006bearer" not in stored_text
    assert "g006token" not in stored_text


def test_idempotency_replay_emits_replay_audit_row(tmp_path: Path) -> None:
    # Given: an idempotent create already exists.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    kwargs = {
        "session_id": "session-replay",
        "run_id": "run-replay",
        "goal_contract_id": "goal-replay",
        "resume_token": RESUME_TOKEN,
        "message": "start replay",
        "idempotency_key": "idem-replay",
        "authority_fingerprint": "sha256:auth-a",
    }
    store.create_or_replay_session(**kwargs)

    # When: the compatible idempotency request is replayed.
    replayed = store.create_or_replay_session(**kwargs)

    # Then: replay is stable and has its own audit annotation.
    assert replayed.idempotency_replay_stable is True
    assert store.counts().sessions == 1
    assert store.counts().audit_records == 2
    assert _audit_events(db_path) == ["session_created", "session_replayed"]


def test_secret_only_message_difference_triggers_idempotency_conflict_without_secret_persistence(
    tmp_path: Path,
) -> None:
    # Given: two requests share an idempotency key but differ only by secret-like spans.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    create_kwargs = {
        "session_id": "session-secret-diff",
        "run_id": "run-secret-diff",
        "goal_contract_id": "goal-secret-diff",
        "resume_token": RESUME_TOKEN,
        "idempotency_key": "idem-secret-diff",
        "authority_fingerprint": "sha256:auth-a",
    }
    store.create_or_replay_session(
        **create_kwargs,
        message="use sk-first-secret",
    )

    # When: the same idempotency key is replayed with only the secret span changed.
    with pytest.raises(GatewaySessionIdempotencyConflict) as conflict:
        store.create_or_replay_session(
            **create_kwargs,
            message="use sk-second-secret",
        )

    # Then: the replay fails closed and SQLite never stores either raw secret.
    assert conflict.value.reason == "idempotency_conflict"
    assert store.counts().sessions == 1
    stored_text = _sqlite_text(db_path)
    assert "sk-first-secret" not in stored_text
    assert "sk-second-secret" not in stored_text


def test_forced_idempotency_insert_failure_rolls_back_session_mutation(tmp_path: Path) -> None:
    # Given: SQLite fails exactly when the idempotency row is inserted.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_idempotency_insert BEFORE INSERT ON gateway_idempotency "
            "BEGIN SELECT RAISE(ABORT, 'forced idempotency failure'); END;",
        )

    # When: session creation reaches the failing idempotency insert.
    with pytest.raises(GatewaySessionIdempotencyConflict):
        store.create_or_replay_session(
            session_id="session-race",
            run_id="run-race",
            goal_contract_id="goal-race",
            resume_token=RESUME_TOKEN,
            message="race create",
            idempotency_key="idem-race",
            authority_fingerprint="sha256:auth-a",
        )

    # Then: the attempted session mutation was rolled back before audit commit.
    counts = store.counts()
    assert counts.sessions == 0
    assert counts.idempotency_records == 0
    assert counts.audit_records == 1


def test_duplicate_session_id_with_different_idempotency_key_blocks_as_conflict(tmp_path: Path) -> None:
    # Given: a runtime with one persisted session id.
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")
    created = runtime.create_session(_create_request(), _security(AUTH_A), "idem-a")

    # When: a different idempotency key tries to create the same session id.
    conflict = runtime.create_session(_create_request(), _security(AUTH_A), "idem-b")

    # Then: the API returns a typed conflict without mutating session count.
    assert created.decision == "allowed"
    assert conflict.decision == "blocked"
    assert conflict.reason == "idempotency_conflict"
    assert conflict.status_code == 409
    assert conflict.gateway_session_count == 1


def test_resume_denies_authority_fingerprint_mismatch(tmp_path: Path) -> None:
    # Given: a session created under one loopback authorization token.
    db_path = tmp_path / "gateway.sqlite"
    runtime = GatewayApiRuntime(db_path=db_path)
    runtime.create_session(_create_request(), _security(AUTH_A), "idem-authority")

    # When: another valid loopback token tries to resume with the known resume token.
    denied = runtime.resume_session(
        "session-g006-review",
        GatewaySessionResumeRequest(resume_token=RESUME_TOKEN, message="resume"),
        _security(AUTH_B, path="/v1/gateway/sessions/session-g006-review/resume"),
    )

    # Then: resume fails closed and no raw auth token is persisted.
    assert denied.decision == "blocked"
    assert denied.reason == "unauthenticated"
    assert denied.status_code == 401
    assert denied.gateway_session_count == 1
    stored_text = _sqlite_text(db_path)
    assert AUTH_A not in stored_text
    assert AUTH_B not in stored_text


def _create_request() -> GatewaySessionCreateRequest:
    return GatewaySessionCreateRequest(**_create_body())


def _create_body() -> JsonPayload:
    return {
        "session_id": "session-g006-review",
        "run_id": "run-g006-review",
        "goal_contract_id": "goal-g006-review",
        "resume_token": RESUME_TOKEN,
        "message": "create",
    }


def _security(token: str, *, path: str = "/v1/gateway/sessions") -> GatewaySecurityRequestContext:
    return GatewaySecurityRequestContext(
        method="POST",
        path=path,
        host="127.0.0.1",
        client_host="127.0.0.1",
        authorization_header="Bearer {0}".format(token),
        expected_token=token,
    )


def _sqlite_text(db_path: Path) -> str:
    with sqlite3.connect(db_path) as connection:
        rows = []
        for table_name in ("gateway_sessions", "gateway_idempotency", "gateway_audit"):
            rows.extend(connection.execute("SELECT * FROM {0}".format(table_name)).fetchall())
    return "\n".join(str(row) for row in rows)


def _audit_events(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        return [row[0] for row in connection.execute("SELECT event FROM gateway_audit ORDER BY audit_id")]
