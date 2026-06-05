from __future__ import annotations

import http.client
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Final, Union
from urllib.parse import urlsplit

import pytest

from zeus_agent.gateway_runtime.server import GatewayLoopbackServer

AUTH_A: Final = "g006-http-auth-token-a"
RESUME_TOKEN: Final = "g006-http-resume-token"
JsonPayload = dict[str, Union[str, int, bool, None]]


@pytest.fixture
def server(tmp_path: Path) -> Iterator[GatewayLoopbackServer]:
    instance = GatewayLoopbackServer(
        bind="127.0.0.1",
        port=0,
        db_path=tmp_path / "gateway.sqlite",
        ready_file=None,
        loopback_token=AUTH_A,
    )
    instance.start()
    try:
        yield instance
    finally:
        instance.shutdown()


def test_gateway_session_store_initializes_gateway_tables(tmp_path: Path) -> None:
    from zeus_agent.gateway_runtime.session_store import SQLiteGatewaySessionStore

    db_path = tmp_path / "gateway.sqlite"
    SQLiteGatewaySessionStore(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'",
            )
        }

    assert {"gateway_sessions", "gateway_idempotency", "gateway_audit"} <= table_names


def test_create_or_replay_session_persists_once_and_replays_stably(tmp_path: Path) -> None:
    from zeus_agent.gateway_runtime.session_store import SQLiteGatewaySessionStore

    store = SQLiteGatewaySessionStore(tmp_path / "gateway.sqlite")

    created = store.create_or_replay_session(
        session_id="session-g006-001",
        run_id="run-g006-001",
        goal_contract_id="goal-g006-001",
        resume_token="secret-token-g006",
        message="start gateway session",
        idempotency_key="idem-g006-session",
        authority_fingerprint="sha256:auth",
    )
    replayed = store.create_or_replay_session(
        session_id="session-g006-001",
        run_id="run-g006-001",
        goal_contract_id="goal-g006-001",
        resume_token="secret-token-g006",
        message="start gateway session",
        idempotency_key="idem-g006-session",
        authority_fingerprint="sha256:auth",
    )

    assert created.idempotency_replay_stable is False
    assert replayed.idempotency_replay_stable is True
    assert replayed.session_id == created.session_id
    assert store.counts().sessions == 1
    assert store.counts().idempotency_records == 1
    assert store.audit_summary().audit_records == 2


def test_conflicting_idempotency_replay_fails_closed(tmp_path: Path) -> None:
    from zeus_agent.gateway_runtime.session_store import (
        GatewaySessionIdempotencyConflict,
        SQLiteGatewaySessionStore,
    )

    store = SQLiteGatewaySessionStore(tmp_path / "gateway.sqlite")
    store.create_or_replay_session(
        session_id="session-g006-001",
        run_id="run-g006-001",
        goal_contract_id="goal-g006-001",
        resume_token="secret-token-g006",
        message="start gateway session",
        idempotency_key="idem-g006-session",
        authority_fingerprint="sha256:auth",
    )

    with pytest.raises(GatewaySessionIdempotencyConflict) as conflict:
        store.create_or_replay_session(
            session_id="session-g006-002",
            run_id="run-g006-001",
            goal_contract_id="goal-g006-001",
            resume_token="secret-token-g006",
            message="changed gateway session",
            idempotency_key="idem-g006-session",
            authority_fingerprint="sha256:auth",
        )

    assert conflict.value.reason == "idempotency_conflict"
    assert store.counts().sessions == 1
    assert store.counts().idempotency_records == 1


def test_resume_session_requires_token_match_without_token_leak(tmp_path: Path) -> None:
    from zeus_agent.gateway_runtime.session_store import SQLiteGatewaySessionStore

    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    store.create_or_replay_session(
        session_id="session-g006-001",
        run_id="run-g006-001",
        goal_contract_id="goal-g006-001",
        resume_token="secret-token-g006",
        message="start gateway session",
        idempotency_key="idem-g006-session",
        authority_fingerprint="sha256:auth",
    )

    resumed = store.resume_session(
        session_id="session-g006-001",
        resume_token="secret-token-g006",
        message="resume gateway session",
        authority_fingerprint="sha256:auth",
    )
    denied = store.resume_session(
        session_id="session-g006-001",
        resume_token="wrong-token-g006",
        message="resume gateway session",
        authority_fingerprint="sha256:auth",
    )

    with sqlite3.connect(db_path) as connection:
        rows = []
        for table_name in (
            "gateway_sessions",
            "gateway_idempotency",
            "gateway_audit",
        ):
            rows.extend(connection.execute(f"SELECT * FROM {table_name}").fetchall())
        stored_text = "\n".join(str(row) for row in rows)

    assert resumed is not None
    assert resumed.session_id == "session-g006-001"
    assert denied is None
    assert "secret-token-g006" not in repr(resumed)
    assert "secret-token-g006" not in repr(store.audit_summary())
    assert "secret-token-g006" not in stored_text


def test_record_block_audits_without_side_effects(tmp_path: Path) -> None:
    from zeus_agent.gateway_runtime.session_store import SQLiteGatewaySessionStore

    store = SQLiteGatewaySessionStore(tmp_path / "gateway.sqlite")

    store.record_block(
        session_id="session-g006-blocked",
        run_id="run-g006-001",
        goal_contract_id="goal-g006-001",
        reason="policy_blocked",
        message="blocked before side effects",
    )

    counts = store.counts()
    summary = store.audit_summary()
    assert counts.sessions == 0
    assert counts.idempotency_records == 0
    assert counts.audit_records == 1
    assert counts.handler_executed is False
    assert counts.network_opened is False
    assert counts.side_effects is False
    assert summary.handler_executed is False
    assert summary.network_opened is False
    assert summary.side_effects is False


def test_http_embedded_provider_token_like_identity_is_malformed_without_persistence(
    server: GatewayLoopbackServer,
) -> None:
    # Given: an HTTP create request embeds a provider-token-like span in a public identity.
    raw_secret = "session-ghp_abc123"
    body = {
        "session_id": raw_secret,
        "run_id": "run-g006-http-provider",
        "goal_contract_id": "goal-g006-http-provider",
        "resume_token": RESUME_TOKEN,
        "message": "create",
    }

    # When: the loopback HTTP boundary evaluates the request.
    status, payload, text = _request(server, body)

    # Then: it is rejected as malformed and the raw value is absent from response and SQLite.
    assert status == 400
    assert payload["reason"] == "malformed_request"
    assert payload["gateway_session_count"] == 0
    assert raw_secret not in "{0}\n{1}".format(text, _sqlite_text(server.db_path))


def _request(server: GatewayLoopbackServer, body: dict[str, str]) -> tuple[int, JsonPayload, str]:
    parsed = urlsplit(server.base_url)
    assert parsed.hostname is not None
    assert parsed.port is not None
    encoded = json.dumps(body).encode("utf-8")
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
    try:
        connection.putrequest("POST", "/v1/gateway/sessions")
        connection.putheader("Authorization", "Bearer {0}".format(AUTH_A))
        connection.putheader("Idempotency-Key", "idem-g006-http-provider")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(len(encoded)))
        connection.endheaders(encoded)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        payload = json.loads(text)
        assert isinstance(payload, dict)
        return response.status, payload, text
    finally:
        connection.close()


def _sqlite_text(db_path: Path) -> str:
    with sqlite3.connect(db_path) as connection:
        rows = []
        for table_name in ("gateway_sessions", "gateway_idempotency", "gateway_audit"):
            rows.extend(connection.execute(f"SELECT * FROM {table_name}").fetchall())
    return "\n".join(str(row) for row in rows)
