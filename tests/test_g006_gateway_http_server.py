from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import pytest
from pydantic import JsonValue

from zeus_agent.gateway_runtime.server import (
    GatewayLoopbackServer,
    GatewayLoopbackServerBindError,
)

AUTH_TOKEN: Final = "g006-http-auth-token"
RESUME_TOKEN: Final = "g006-http-resume-token"
JsonPayload = dict[str, JsonValue]


@pytest.fixture
def server(tmp_path: Path) -> Iterator[GatewayLoopbackServer]:
    instance = GatewayLoopbackServer(
        bind="127.0.0.1",
        port=0,
        db_path=tmp_path / "gateway.sqlite",
        ready_file=None,
        loopback_token=AUTH_TOKEN,
    )
    instance.start()
    try:
        yield instance
    finally:
        instance.shutdown()


def test_http_server_creates_resumes_and_audits_session(server: GatewayLoopbackServer) -> None:
    # Given: a started loopback HTTP server with authenticated gateway traffic.
    create_body = _create_body()

    # When: session create, resume, and audit routes are called through HTTP.
    create_status, create_payload, create_text = _request(
        server,
        "POST",
        "/v1/gateway/sessions",
        body=create_body,
        headers={"Idempotency-Key": "idem-g006-http"},
    )
    resume_status, resume_payload, resume_text = _request(
        server,
        "POST",
        "/v1/gateway/sessions/session-g006-http/resume",
        body={"resume_token": RESUME_TOKEN, "message": "resume over http"},
    )
    audit_status, audit_payload, _ = _request(server, "GET", "/v1/gateway/audit")

    # Then: all successful responses expose HTTP-surface proof without secret echo.
    assert create_status == 200
    assert create_payload["session_persisted"] is True
    assert create_payload["loopback_http_opened"] is True
    assert create_payload["C001"] is True
    assert create_payload["C002"] is True
    assert create_payload["C003"] is True
    assert create_payload["live_production_claimed"] is False
    assert RESUME_TOKEN not in create_text
    assert AUTH_TOKEN not in create_text
    assert resume_status == 200
    assert resume_payload["resume_succeeded"] is True
    assert RESUME_TOKEN not in resume_text
    assert audit_status == 200
    assert audit_payload["gateway_session_count"] == 1
    assert server.request_count() == 3


def test_ready_file_excludes_token_and_is_removed_on_shutdown(tmp_path: Path) -> None:
    # Given: a server configured with a ready-file path.
    ready_file = tmp_path / "gateway-ready.json"
    server = GatewayLoopbackServer(
        bind="127.0.0.1",
        port=0,
        db_path=tmp_path / "gateway.sqlite",
        ready_file=ready_file,
        loopback_token=AUTH_TOKEN,
    )

    # When: the server starts and then shuts down.
    server.start()
    ready_payload = json.loads(ready_file.read_text(encoding="utf-8"))
    server.shutdown()

    # Then: readiness names the loopback endpoint and cleans up without token leakage.
    assert ready_payload["base_url"] == server.base_url
    assert ready_payload["bind"] == "127.0.0.1"
    assert ready_payload["port"] > 0
    assert ready_payload["db_path"] == str(tmp_path / "gateway.sqlite")
    assert AUTH_TOKEN not in json.dumps(ready_payload)
    assert ready_file.exists() is False
    assert server.shutdown_complete is True


def test_host_header_non_loopback_returns_exact_block_reason(server: GatewayLoopbackServer) -> None:
    # Given: a local TCP client with a non-loopback Host header.
    # When: the request reaches the audit route.
    status, payload, _ = _request(
        server,
        "GET",
        "/v1/gateway/audit",
        host_header="evil.example",
    )

    # Then: the security policy blocks it with the exact host reason.
    assert status == 403
    assert payload["decision"] == "blocked"
    assert payload["reason"] == "non_loopback_blocked"
    assert payload["loopback_http_opened"] is True
    assert payload["handler_executed"] is False


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("/v1/gateway/webhooks", "webhook_blocked"),
        ("/v1/gateway/external-delivery", "external_delivery_blocked"),
        ("/v1/gateway/standing-orders", "standing_order_blocked"),
    ],
)
def test_blocked_surfaces_return_exact_reasons(
    server: GatewayLoopbackServer,
    path: str,
    reason: str,
) -> None:
    # Given: authenticated loopback traffic to a blocked gateway surface.
    # When: the blocked surface is posted through the HTTP server.
    status, payload, _ = _request(server, "POST", path, body={})

    # Then: the route fails closed with its exact reason and no side-effect flags.
    assert status == 403
    assert payload["reason"] == reason
    assert payload["loopback_http_opened"] is True
    assert payload["external_delivery_opened"] is False
    assert payload["webhook_registered"] is False
    assert payload["standing_order_created"] is False


def test_malformed_json_returns_safe_400_without_body_echo(
    server: GatewayLoopbackServer,
) -> None:
    # Given: a malformed request body containing secret-shaped material.
    raw_body = '{{"resume_token":"{0}"'.format(RESUME_TOKEN)

    # When: the body is posted to the create route.
    status, payload, response_text = _request(
        server,
        "POST",
        "/v1/gateway/sessions",
        body=raw_body,
        headers={"Idempotency-Key": "idem-malformed"},
    )

    # Then: only the typed malformed reason is returned.
    assert status == 400
    assert payload["reason"] == "malformed_request"
    assert RESUME_TOKEN not in response_text
    assert raw_body not in response_text


def test_non_loopback_bind_is_rejected_before_start(tmp_path: Path) -> None:
    # Given / When / Then: public bind targets fail before ThreadingHTTPServer starts.
    with pytest.raises(GatewayLoopbackServerBindError) as raised:
        GatewayLoopbackServer(
            bind="0.0.0.0",
            port=0,
            db_path=tmp_path / "gateway.sqlite",
            ready_file=None,
            loopback_token=AUTH_TOKEN,
        )
    assert raised.value.reason == "non_loopback_bind_blocked"


def test_shutdown_closes_server_socket(server: GatewayLoopbackServer) -> None:
    # Given: a running loopback server with an open base URL.
    parsed = urlsplit(server.base_url)
    assert parsed.hostname is not None
    assert parsed.port is not None

    # When: shutdown is requested.
    server.shutdown()

    # Then: the closed listener no longer accepts HTTP requests.
    assert server.shutdown_complete is True
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=0.2)
    with pytest.raises(OSError):
        connection.request("GET", "/v1/gateway/audit")


def _request(
    server: GatewayLoopbackServer,
    method: str,
    path: str,
    *,
    body: JsonPayload | str | None = None,
    headers: dict[str, str] | None = None,
    host_header: str | None = None,
) -> tuple[int, JsonPayload, str]:
    parsed = urlsplit(server.base_url)
    assert parsed.hostname is not None
    assert parsed.port is not None
    payload = _encode_body(body)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
    try:
        connection.putrequest(method, path, skip_host=host_header is not None)
        if host_header is not None:
            connection.putheader("Host", host_header)
        connection.putheader("Authorization", "Bearer {0}".format(AUTH_TOKEN))
        for key, value in (headers or {}).items():
            connection.putheader(key, value)
        if payload:
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(len(payload)))
        connection.endheaders(payload if payload else None)
        response = connection.getresponse()
        raw_text = response.read().decode("utf-8")
        decoded = json.loads(raw_text)
        assert isinstance(decoded, dict)
        return response.status, decoded, raw_text
    finally:
        connection.close()


def _encode_body(body: JsonPayload | str | None) -> bytes:
    if body is None:
        return b""
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body).encode("utf-8")


def _create_body() -> JsonPayload:
    return {
        "session_id": "session-g006-http",
        "run_id": "run-g006-http",
        "goal_contract_id": "goal-g006-http",
        "resume_token": RESUME_TOKEN,
        "message": "create over http",
    }
