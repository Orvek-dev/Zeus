from __future__ import annotations

import http.client
import json
import socket
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import pytest
from pydantic import JsonValue

from zeus_agent.gateway_runtime.server import GatewayLoopbackServer

AUTH_A: Final = "g006-http-auth-token-a"
AUTH_B: Final = "g006-http-auth-token-b"
RESUME_TOKEN: Final = "g006-http-resume-token"
SECRET_MESSAGE: Final = "use sk-g006raw Bearer g006bearer token=g006token"
JsonPayload = dict[str, JsonValue]


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


def test_http_duplicate_session_id_conflict_returns_409_without_stack_trace(server: GatewayLoopbackServer) -> None:
    # Given: the HTTP gateway has accepted a session create.
    first_status, _, _ = _request(server, "POST", "/v1/gateway/sessions", _create_body(), "idem-a")

    # When: the same session id is created with another idempotency key.
    status, payload, text = _request(server, "POST", "/v1/gateway/sessions", _create_body(), "idem-b")

    # Then: HTTP returns a typed 409 conflict and leaves one session row.
    assert first_status == 200
    assert status == 409
    assert payload["reason"] == "idempotency_conflict"
    assert payload["gateway_session_count"] == 1
    _assert_blocked_audit_payload(payload)
    assert all(value not in text for value in ("IntegrityError", "Traceback"))
    assert _session_count(server.db_path) == 1


def test_http_unauthorized_oversized_body_is_audited_before_body_parse(server: GatewayLoopbackServer) -> None:
    # Given: an unauthorized create request with oversized malformed secret body.
    raw_body = ("{{" + SECRET_MESSAGE) * 5000

    # When: it is posted with no bearer authorization.
    status, payload, text = _request_raw(
        server,
        "POST",
        "/v1/gateway/sessions",
        raw_body.encode("utf-8"),
        {"Idempotency-Key": "idem-unauth"},
        auth_token=None,
    )

    # Then: auth fails first, an audit row exists, and the body secret never echoes.
    assert status == 401
    assert payload["reason"] == "unauthenticated"
    assert payload["audit_records"] == 1
    _assert_blocked_audit_payload(payload)
    assert SECRET_MESSAGE not in "{0}\n{1}".format(text, _sqlite_text(server.db_path))


@pytest.mark.parametrize(
    ("path", "body", "idem", "expected_status", "expected_reason"),
    [
        ("/v1/gateway/sessions", "{{bad-json", "idem-bad-json", 400, "malformed_request"),
        (
            "/v1/gateway/sessions",
            {
                "session_id": "session-g006-review",
                "run_id": "run-g006-review",
                "goal_contract_id": "goal-g006-review",
                "resume_token": RESUME_TOKEN,
                "message": "create",
            },
            None,
            400,
            "malformed_request",
        ),
        ("/v1/gateway/unknown", {}, "idem-unknown", 400, "malformed_request"),
        ("/v1/gateway/webhooks/extra", {}, "idem-webhook", 403, "webhook_blocked"),
    ],
)
def test_http_fail_closed_boundary_errors_create_audit_rows(
    server: GatewayLoopbackServer,
    path: str,
    body: JsonPayload | str,
    idem: str | None,
    expected_status: int,
    expected_reason: str,
) -> None:
    # Given / When: a malformed, missing-idempotency, unknown, or blocked-prefix request is posted.
    status, payload, _ = _request(server, "POST", path, body, idem)

    # Then: the HTTP response is typed and audited through the runtime path.
    assert status == expected_status
    assert payload["reason"] == expected_reason
    assert payload["audit_records"] == 1
    _assert_blocked_audit_payload(payload)


@pytest.mark.parametrize(
    ("field_name", "idempotency_key"),
    [
        ("session_id", "idem-http-secret-field"),
        ("run_id", "idem-http-secret-field"),
        ("goal_contract_id", "idem-http-secret-field"),
        (None, "sk-g006-http-idempotency-secret"),
    ],
)
def test_http_secret_like_identity_and_idempotency_key_are_rejected_before_persistence(
    server: GatewayLoopbackServer,
    field_name: str | None,
    idempotency_key: str,
) -> None:
    # Given: a create request includes a secret-shaped identity field or idempotency key.
    body = _create_body()
    raw_secret = idempotency_key if field_name is None else "sk-g006-http-{0}-secret".format(field_name)
    if field_name is not None:
        body[field_name] = raw_secret

    # When: the HTTP gateway evaluates the request.
    status, payload, text = _request(server, "POST", "/v1/gateway/sessions", body, idempotency_key)

    # Then: the request is malformed, audited through a sanitized path, and not persisted.
    assert status == 400
    assert payload["reason"] == "malformed_request"
    _assert_blocked_audit_payload(payload)
    assert payload["gateway_session_count"] == 0
    assert raw_secret not in "{0}\n{1}".format(text, _sqlite_text(server.db_path))


def test_http_resume_secret_like_path_session_id_is_sanitized_before_audit(server: GatewayLoopbackServer) -> None:
    # Given: a resume URL path carries a secret-shaped session id.
    raw_secret = "sk-g006-http-resume-secret"

    # When: the HTTP gateway evaluates the resume request.
    status, payload, text = _request(
        server, "POST", f"/v1/gateway/sessions/{raw_secret}/resume", {"resume_token": RESUME_TOKEN, "message": "resume"}, None
    )

    # Then: the request fails closed, is audited, and never stores the raw path secret.
    assert (status, payload["reason"], payload["audit_records"]) == (401, "unauthenticated", 1)
    _assert_blocked_audit_payload(payload)
    assert raw_secret not in "{0}\n{1}".format(text, _sqlite_text(server.db_path))


def test_http_invalid_security_context_is_audited_with_sanitized_fallback(server: GatewayLoopbackServer) -> None:
    # Given: an authenticated HTTP request has an invalid request-target path.
    raw_request = (
        "GET v1/gateway/audit HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        "Authorization: Bearer {0}\r\n"
        "Content-Length: 0\r\n\r\n"
    ).format(AUTH_A).encode("utf-8")

    # When: the request cannot build the normal security context.
    status, payload, text = _raw_socket_request(server, raw_request)

    # Then: it fails closed with an audit row and no dangerous side effects.
    assert status == 400
    assert payload["reason"] == "malformed_request"
    assert payload["audit_records"] == 1
    _assert_blocked_audit_payload(payload)
    assert "Traceback" not in text
    assert "/v1/gateway/malformed-security-context" in _sqlite_text(server.db_path)


def test_http_resume_denies_different_loopback_authority(server: GatewayLoopbackServer) -> None:
    # Given: a session created under AUTH_A.
    create_status, _, _ = _request(server, "POST", "/v1/gateway/sessions", _create_body(), "idem-authority")
    server._state.expected_token = AUTH_B

    # When: AUTH_B knows the resume token but not the original authority.
    status, payload, text = _request(
        server,
        "POST",
        "/v1/gateway/sessions/session-g006-review/resume",
        {"resume_token": RESUME_TOKEN, "message": "resume"},
        None,
        auth_token=AUTH_B,
    )

    # Then: resume is denied and neither raw token is stored or echoed.
    assert create_status == 200
    assert status == 401
    assert payload["reason"] == "unauthenticated"
    assert payload["gateway_session_count"] == 1
    _assert_blocked_audit_payload(payload)
    assert all(token not in text for token in (AUTH_A, AUTH_B))
    stored_text = _sqlite_text(server.db_path)
    assert all(token not in stored_text for token in (AUTH_A, AUTH_B))


def _request(
    server: GatewayLoopbackServer,
    method: str,
    path: str,
    body: JsonPayload | str,
    idempotency_key: str | None,
    *,
    auth_token: str | None = AUTH_A,
) -> tuple[int, JsonPayload, str]:
    headers = {} if idempotency_key is None else {"Idempotency-Key": idempotency_key}
    return _request_raw(server, method, path, _encode_body(body), headers, auth_token=auth_token)


def _request_raw(
    server: GatewayLoopbackServer,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    *,
    auth_token: str | None,
) -> tuple[int, JsonPayload, str]:
    parsed = urlsplit(server.base_url)
    assert parsed.hostname is not None
    assert parsed.port is not None
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
    try:
        connection.putrequest(method, path)
        if auth_token is not None:
            connection.putheader("Authorization", "Bearer {0}".format(auth_token))
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        payload = json.loads(text)
        assert isinstance(payload, dict)
        return response.status, payload, text
    finally:
        connection.close()


def _raw_socket_request(server: GatewayLoopbackServer, raw_request: bytes) -> tuple[int, JsonPayload, str]:
    parsed = urlsplit(server.base_url)
    assert parsed.hostname is not None
    assert parsed.port is not None
    with socket.create_connection((parsed.hostname, parsed.port), timeout=2) as connection:
        connection.sendall(raw_request)
        response_bytes = _read_socket_response(connection)
    text = response_bytes.decode("utf-8")
    _, _, body = text.partition("\r\n\r\n")
    status_line = text.splitlines()[0]
    status = int(status_line.split()[1])
    payload = json.loads(body)
    assert isinstance(payload, dict)
    return status, payload, text


def _read_socket_response(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(4096)
        if chunk == b"":
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _create_body() -> JsonPayload:
    return {
        "session_id": "session-g006-review",
        "run_id": "run-g006-review",
        "goal_contract_id": "goal-g006-review",
        "resume_token": RESUME_TOKEN,
        "message": "create",
    }


def _encode_body(body: JsonPayload | str) -> bytes:
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body).encode("utf-8")


def _sqlite_text(db_path: Path) -> str:
    with sqlite3.connect(db_path) as connection:
        rows = []
        for table_name in ("gateway_sessions", "gateway_idempotency", "gateway_audit"):
            rows.extend(connection.execute("SELECT * FROM {0}".format(table_name)).fetchall())
    return "\n".join(str(row) for row in rows)


def _session_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM gateway_sessions").fetchone()
    return int(row[0])


def _assert_blocked_audit_payload(payload: JsonPayload) -> None:
    assert payload["audit_record_created"] is True
    assert payload["handler_executed"] is False
    assert payload["side_effect_count"] == 0
    assert payload["network_opened"] is False
    assert payload["external_delivery_attempted"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["webhook_registered"] is False
    assert payload["standing_order_created"] is False
    assert payload["credential_material_accessed"] is False
