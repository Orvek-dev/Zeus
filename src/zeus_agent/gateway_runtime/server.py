from __future__ import annotations

import json
import signal
import socket
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import FrameType
from typing import Final

from pydantic import JsonValue, ValidationError

from zeus_agent.gateway_runtime.api import GatewayApiRuntime
from zeus_agent.gateway_runtime.models import (
    GatewayApiResponse,
    GatewaySessionCreateRequest,
    GatewaySessionResumeRequest,
)
from zeus_agent.gateway_runtime.security import GatewaySecurityRequestContext
from zeus_agent.gateway_runtime.server_support import (
    http_payload,
    malformed_security_response,
    path_only,
    resume_session_id,
)

JsonPayload = dict[str, JsonValue]
_LOOPBACK_BINDS: Final = frozenset(("127.0.0.1", "localhost", "::1"))
_MAX_BODY_BYTES: Final = 64 * 1024


@dataclass(frozen=True, slots=True)
class GatewayLoopbackServerBindError(RuntimeError):
    bind: str
    reason: str = "non_loopback_bind_blocked"

    def __str__(self) -> str:
        return "{0}: {1}".format(self.reason, self.bind)


class _IPv6ThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


@dataclass(slots=True)
class _GatewayLoopbackState:
    runtime: GatewayApiRuntime
    expected_token: str
    request_total: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_request(self) -> None:
        with self.lock:
            self.request_total += 1

    def request_count(self) -> int:
        with self.lock:
            return self.request_total


class GatewayLoopbackServer:
    def __init__(self, *, bind: str, port: int, db_path: Path, ready_file: Path | None, loopback_token: str) -> None:
        normalized_bind = bind.strip().lower()
        if normalized_bind not in _LOOPBACK_BINDS:
            raise GatewayLoopbackServerBindError(bind=bind)
        self.bind = normalized_bind
        self.db_path = db_path
        self.ready_file = ready_file
        self._state = _GatewayLoopbackState(GatewayApiRuntime(db_path=db_path), loopback_token)
        self._server = _make_server(normalized_bind, port, _handler_for(self._state))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._started = False
        self.shutdown_complete = False

    @property
    def base_url(self) -> str:
        host = self._server.server_address[0]
        port = self._server.server_address[1]
        if host == "::1":
            return "http://[::1]:{0}".format(port)
        return "http://{0}:{1}".format(host, port)

    def start(self) -> None:
        if self._started:
            return
        self._thread.start()
        self._started = True
        self._write_ready_file()

    def shutdown(self) -> None:
        if self.shutdown_complete:
            return
        if self._started:
            self._server.shutdown()
        self._server.server_close()
        if self._started:
            self._thread.join(timeout=2)
        self._remove_ready_file()
        self.shutdown_complete = not self._thread.is_alive()

    def request_count(self) -> int:
        return self._state.request_count()

    def _write_ready_file(self) -> None:
        if self.ready_file is None:
            return
        payload: dict[str, str | int] = {
            "base_url": self.base_url,
            "bind": self.bind,
            "port": self._server.server_address[1],
            "db_path": str(self.db_path),
        }
        self.ready_file.parent.mkdir(parents=True, exist_ok=True)
        self.ready_file.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def _remove_ready_file(self) -> None:
        if self.ready_file is not None:
            self.ready_file.unlink(missing_ok=True)


def run_gateway_loopback_server(bind: str, port: int, db_path: Path, ready_file: Path | None, loopback_token: str) -> None:
    server = GatewayLoopbackServer(bind=bind, port=port, db_path=db_path, ready_file=ready_file, loopback_token=loopback_token)
    stop = threading.Event()

    def handle_sigterm(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    previous = signal.signal(signal.SIGTERM, handle_sigterm)
    try:
        server.start()
        while not stop.wait(0.25):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        signal.signal(signal.SIGTERM, previous)


def _make_server(bind: str, port: int, handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    if bind == "::1":
        return _IPv6ThreadingHTTPServer((bind, port), handler)
    return ThreadingHTTPServer((bind, port), handler)


def _handler_for(state: _GatewayLoopbackState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.record_request()
            path = path_only(self.path)
            try:
                security = self._security("GET", path)
            except ValidationError:
                self._send_gateway(self._malformed_security_response("GET"))
                return
            blocked = state.runtime.preflight_block(security)
            if blocked is not None:
                self._send_gateway(blocked)
                return
            if path == "/v1/gateway/audit":
                self._send_gateway(state.runtime.audit_summary(security))
                return
            self._send_gateway(state.runtime.malformed_request(security))

        def do_POST(self) -> None:
            state.record_request()
            path = path_only(self.path)
            try:
                security = self._security("POST", path)
            except ValidationError:
                self._send_gateway(self._malformed_security_response("POST"))
                return
            blocked = state.runtime.preflight_block(security)
            if blocked is not None:
                self._send_gateway(blocked)
                return
            if path == "/v1/gateway/sessions":
                self._handle_create(security)
                return
            session_id = resume_session_id(path)
            if session_id is not None:
                self._handle_resume(session_id, security)
                return
            self._send_gateway(state.runtime.malformed_request(security))

        def log_message(self, format: str, *args: object) -> None:
            return None

        def _handle_create(self, security: GatewaySecurityRequestContext) -> None:
            idempotency_key = self.headers.get("Idempotency-Key", "").strip()
            if idempotency_key == "":
                self._send_gateway(state.runtime.malformed_request(security))
                return
            try:
                request = GatewaySessionCreateRequest(**self._json_body())
            except GatewayLoopbackBodyTooLarge:
                self._send_gateway(state.runtime.malformed_request(security, status_code=413))
                return
            except (GatewayLoopbackMalformedRequest, TypeError, ValidationError):
                self._send_gateway(state.runtime.malformed_request(security))
                return
            self._send_gateway(state.runtime.create_session(request, security, idempotency_key))

        def _handle_resume(self, session_id: str, security: GatewaySecurityRequestContext) -> None:
            try:
                request = GatewaySessionResumeRequest(**self._json_body())
            except GatewayLoopbackBodyTooLarge:
                self._send_gateway(state.runtime.malformed_request(security, status_code=413))
                return
            except (GatewayLoopbackMalformedRequest, TypeError, ValidationError):
                self._send_gateway(state.runtime.malformed_request(security))
                return
            self._send_gateway(state.runtime.resume_session(session_id, request, security))

        def _security(self, method: str, path: str) -> GatewaySecurityRequestContext:
            return GatewaySecurityRequestContext(
                method=method,
                path=path,
                host=self.headers.get("Host", ""),
                client_host=self.client_address[0],
                authorization_header=self.headers.get("Authorization"),
                expected_token=state.expected_token,
            )

        def _malformed_security_response(self, method: str) -> GatewayApiResponse:
            return malformed_security_response(
                state.runtime,
                method=method,
                authorization_header=self.headers.get("Authorization"),
                expected_token=state.expected_token,
            )

        def _json_body(self) -> JsonPayload:
            raw_length = self.headers.get("Content-Length", "0")
            if not raw_length.isdigit():
                raise GatewayLoopbackMalformedRequest
            body_size = int(raw_length)
            if body_size > _MAX_BODY_BYTES:
                raise GatewayLoopbackBodyTooLarge
            raw_body = self.rfile.read(body_size)
            try:
                decoded = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise GatewayLoopbackMalformedRequest from error
            if not isinstance(decoded, dict):
                raise GatewayLoopbackMalformedRequest
            return decoded

        def _send_gateway(self, response: GatewayApiResponse) -> None:
            payload = http_payload(response)
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


class GatewayLoopbackMalformedRequest(RuntimeError):
    pass


class GatewayLoopbackBodyTooLarge(RuntimeError):
    pass


__all__: Final = ("GatewayLoopbackServer", "GatewayLoopbackServerBindError", "run_gateway_loopback_server")
