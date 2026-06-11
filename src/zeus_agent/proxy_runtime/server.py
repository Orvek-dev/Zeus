from __future__ import annotations

import json
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

from pydantic import JsonValue

from zeus_agent.decision_api_runtime import HostKind

from .engine import LlmProxyEngine, ProxyHttpResult, ProxySession

_FORWARD_HEADERS = ("authorization", "x-api-key", "anthropic-version", "openai-organization")
_UPSTREAM_TIMEOUT_SECONDS = 600


def session_from_headers(headers) -> ProxySession:
    """The session map: hosts identify themselves with x-zeus-* headers; an
    unlabelled client still gets governed under the default proxy session."""
    host_raw = (headers.get("x-zeus-host") or "").strip().lower().replace("-", "_")
    try:
        host = HostKind(host_raw) if host_raw else HostKind.console
    except ValueError:
        host = HostKind.console
    return ProxySession(
        principal_id=(headers.get("x-zeus-principal") or "agent.llm_proxy").strip(),
        session_id=(headers.get("x-zeus-session") or "llm-proxy.default").strip(),
        objective_id=(headers.get("x-zeus-objective") or "").strip() or None,
        host=host,
        run_id=(headers.get("x-zeus-run") or "").strip() or None,
    )


def make_proxy_handler(
    engine: LlmProxyEngine,
    upstream_base: str,
    *,
    save_state=None,
    api=None,
    v1_token_required: bool = False,
    pairing=None,
) -> type[BaseHTTPRequestHandler]:
    base = upstream_base.rstrip("/")

    class ZeusProxyHandler(BaseHTTPRequestHandler):
        server_version = "ZeusLLMProxy/1.0"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return  # request lines routinely carry prompts; keep them out of stderr

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if api is not None and path.startswith("/zeus/"):
                handled = api.handle("GET", self.path, dict(self.headers.items()), b"")
                if handled is not None:
                    self._write_json(handled[0], handled[1])
                    return
            if path in {"/health", "/v1/health"}:
                self._write_json(200, {"status": "ok", "gate": "llm_proxy"})
                return
            if path == "/v1/models":
                if self._v1_session() is None:
                    return  # 401 already written
                self._write_result(engine.models())
                return
            self._write_json(404, {"error": {"message": "unknown path", "type": "zeus_proxy"}})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if api is not None and path.startswith("/zeus/"):
                raw = self._read_raw()
                handled = api.handle("POST", self.path, dict(self.headers.items()), raw)
                if handled is not None:
                    self._write_json(handled[0], handled[1])
                    if save_state is not None:
                        save_state()
                    return
            body = self._read_body()
            session = self._v1_session()
            if session is None:
                return  # 401 already written: /v1 needs a token on this bind
            if path == "/v1/chat/completions":
                if bool(body.get("stream")):
                    self._handle_stream(body, session)
                else:
                    self._write_result(
                        engine.chat_completion(body, session, self._upstream(path))
                    )
            elif path == "/v1/responses":
                self._write_result(engine.responses(body, session, self._upstream(path)))
            else:
                self._write_json(404, {"error": {"message": "unknown path", "type": "zeus_proxy"}})
            if save_state is not None:
                save_state()

        # ------------------------------------------------------------ /v1 auth
        def _v1_session(self) -> Optional[ProxySession]:
            """The session for a /v1 request. When v1 auth is required, a valid
            x-zeus-v1-token is mandatory and its registration — not the
            spoofable x-zeus-* headers — decides host/principal. Returns None
            after writing a 401 when the token is missing or unknown."""
            session = session_from_headers(self.headers)
            if not v1_token_required:
                return session
            registration = (
                pairing.verify_v1_token(self.headers.get("x-zeus-v1-token"))
                if pairing is not None
                else None
            )
            if registration is None:
                engine.engine.recorder.record_decision(
                    run_id="run.proxy.v1auth",
                    payload={
                        "capability_id": "llm.proxy.v1",
                        "decision": "deny",
                        "reason": "v1_token_required",
                        "surface": "llm_proxy",
                    },
                )
                self._write_json(
                    401,
                    {"error": {"message": "[Zeus] /v1 token required", "type": "zeus_proxy", "code": "v1_token_required"}},
                )
                return None
            # identity comes from the token registration ONLY. If the
            # registered host string is not a known HostKind, fall back to a
            # neutral default — NEVER to the spoofable x-zeus-host header.
            return session.model_copy(
                update={
                    "host": _coerce_host(registration.get("host"), HostKind.console),
                    "principal_id": str(registration.get("principal") or "agent.v1token"),
                }
            )

        # ------------------------------------------------------------ upstream
        def _upstream(self, path: str):
            headers = self._forward_headers()

            def call(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
                request = urllib.request.Request(
                    base + path,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={**headers, "content-type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=_UPSTREAM_TIMEOUT_SECONDS) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                return parsed if isinstance(parsed, dict) else {}

            return call

        def _upstream_stream(self, path: str):
            headers = self._forward_headers()

            def call(payload: dict[str, JsonValue]) -> Iterator[dict[str, JsonValue]]:
                request = urllib.request.Request(
                    base + path,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={**headers, "content-type": "application/json", "accept": "text/event-stream"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=_UPSTREAM_TIMEOUT_SECONDS) as response:
                    for raw_line in response:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                        except ValueError:
                            continue
                        if isinstance(parsed, dict):
                            yield parsed

            return call

        def _handle_stream(self, body: dict[str, JsonValue], session: ProxySession) -> None:
            outcome = engine.chat_completion_stream(
                body, session, self._upstream_stream("/v1/chat/completions")
            )
            if outcome.error is not None:
                self._write_result(outcome.error)
                return
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("cache-control", "no-cache")
            self.end_headers()
            assert outcome.chunks is not None
            for chunk in outcome.chunks:
                self.wfile.write(
                    "data: {0}\n\n".format(json.dumps(chunk, ensure_ascii=False)).encode("utf-8")
                )
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

        # ------------------------------------------------------------- helpers
        def _forward_headers(self) -> dict[str, str]:
            forwarded: dict[str, str] = {}
            for name in _FORWARD_HEADERS:
                value = self.headers.get(name)
                if value:
                    forwarded[name] = value
            return forwarded

        def _read_raw(self) -> bytes:
            length = int(self.headers.get("content-length", "0") or "0")
            return self.rfile.read(length) if length > 0 else b""

        def _read_body(self) -> dict[str, JsonValue]:
            raw = self._read_raw()
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
            except ValueError:
                return {}
            return parsed if isinstance(parsed, dict) else {}

        def _write_result(self, result: ProxyHttpResult) -> None:
            self._write_json(result.status, result.body)

        def _write_json(self, status: int, payload: dict[str, JsonValue]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ZeusProxyHandler


def _coerce_host(name, fallback: HostKind) -> HostKind:
    """A v1 token registers a host string; map it to a HostKind, else keep the
    request's own (the token still wins on principal attribution)."""
    try:
        return HostKind(str(name).strip().lower().replace("-", "_"))
    except (ValueError, AttributeError):
        return fallback


def run_proxy_server(
    *,
    host: str,
    port: int,
    engine: LlmProxyEngine,
    upstream_base: str,
    save_state=None,
    api=None,
    v1_token_required: bool = False,
    pairing=None,
    ready_file: Optional[Path] = None,
) -> None:
    handler = make_proxy_handler(
        engine,
        upstream_base,
        save_state=save_state,
        api=api,
        v1_token_required=v1_token_required,
        pairing=pairing,
    )
    server = ThreadingHTTPServer((host, port), handler)
    if ready_file is not None:
        ready_file.write_text(
            json.dumps({"host": host, "port": server.server_address[1]}), encoding="utf-8"
        )
    try:
        server.serve_forever()
    finally:
        server.server_close()
