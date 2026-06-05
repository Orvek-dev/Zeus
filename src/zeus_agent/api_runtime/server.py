from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from zeus_agent.entry_runtime import ZeusChatRuntime
from zeus_agent.model_runtime.provider_catalog import provider_catalog_payload
from zeus_agent.security.credentials import redact_secret_spans


@dataclass(frozen=True)
class ZeusApiServer:
    host: str
    port: int
    home: Path


def make_api_handler(home: Path) -> type[BaseHTTPRequestHandler]:
    runtime = ZeusChatRuntime(home)
    responses: dict[str, dict[str, object]] = {}

    class ZeusApiHandler(BaseHTTPRequestHandler):
        server_version = "ZeusAPI/0.1"

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/health", "/v1/health"}:
                self._write_json({"status": "ok", "live_production_claimed": False})
                return
            if path == "/v1/capabilities":
                self._write_json(_capabilities_payload())
                return
            if path == "/v1/models":
                self._write_json({"object": "list", "data": provider_catalog_payload()["profiles"]})
                return
            if path.startswith("/v1/responses/"):
                response_id = path.rsplit("/", 1)[-1]
                payload = responses.get(response_id)
                if payload is None:
                    self._write_json({"error": "response_not_found"}, status=404)
                    return
                self._write_json(payload)
                return
            self._write_json({"error": "not_found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            body = self._read_json()
            if path == "/v1/chat/completions":
                payload = _chat_completion(runtime, body)
                self._write_json(payload)
                return
            if path == "/v1/responses":
                payload = _response_create(runtime, body)
                responses[str(payload["id"])] = payload
                self._write_json(payload)
                return
            if path == "/v1/runs":
                payload = {
                    "id": "run_dry_001",
                    "status": "blocked",
                    "reason": "objective_runs_require_wave7_runtime",
                    "live_production_claimed": False,
                }
                self._write_json(payload, status=202)
                return
            self._write_json({"error": "not_found"}, status=404)

        def do_DELETE(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path.startswith("/v1/responses/"):
                response_id = path.rsplit("/", 1)[-1]
                deleted = response_id in responses
                responses.pop(response_id, None)
                self._write_json({"id": response_id, "deleted": deleted})
                return
            self._write_json({"error": "not_found"}, status=404)

        def log_message(self, format: str, *args: object) -> None:
            return None

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return {"_malformed_json": redact_secret_spans(raw)}
            if not isinstance(payload, dict):
                return {}
            return payload

        def _write_json(self, payload: dict[str, object], status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Zeus-Live-Production-Claimed", "false")
            self.end_headers()
            self.wfile.write(data)

    return ZeusApiHandler


def run_api_server(host: str, port: int, home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), make_api_handler(home))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _capabilities_payload() -> dict[str, object]:
    return {
        "object": "zeus.capabilities",
        "entry_surfaces": ["cli", "api"],
        "profiles": ["chat", "research", "work", "live", "strict", "remember", "improve"],
        "live_surfaces_require_lease": True,
        "unknown_mcp_quarantined": True,
        "live_production_claimed": False,
    }


def _extract_message(body: dict[str, Any]) -> str:
    messages = body.get("messages")
    if isinstance(messages, list) and messages:
        last = messages[-1]
        if isinstance(last, dict):
            return redact_secret_spans(str(last.get("content", "")))
    value = body.get("input", body.get("prompt", ""))
    return redact_secret_spans(str(value))


def _chat_completion(runtime: ZeusChatRuntime, body: dict[str, Any]) -> dict[str, object]:
    message = _extract_message(body)
    result = runtime.run_turn(
        message=message or "status",
        session_id=str(body.get("session_id", "api-default")),
        provider_id=str(body.get("provider_id", "fake")),
        profile=str(body.get("profile", "chat")),
    )
    return {
        "id": "chatcmpl_zeus_fake",
        "object": "chat.completion",
        "model": result.model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.assistant_message},
                "finish_reason": "stop",
            },
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "live_production_claimed": False,
    }


def _response_create(runtime: ZeusChatRuntime, body: dict[str, Any]) -> dict[str, object]:
    result = runtime.run_turn(
        message=_extract_message(body) or "status",
        session_id=str(body.get("session_id", "api-default")),
        provider_id=str(body.get("provider_id", "fake")),
        profile=str(body.get("profile", "chat")),
    )
    return {
        "id": "resp_zeus_fake",
        "object": "response",
        "status": "completed",
        "model": result.model_id,
        "output_text": result.assistant_message,
        "live_production_claimed": False,
    }
