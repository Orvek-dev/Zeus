from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass(frozen=True)
class ProviderHttpRecord:
    path: str
    body: str


class Wave16ProviderHttpServer:
    def __init__(self) -> None:
        self.records: list[ProviderHttpRecord] = []
        handler = _handler_for(self.records)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.shutdown_complete = False

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return "http://{0}:{1}".format(host, port)

    def start(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        self.shutdown_complete = not self._thread.is_alive()

    def request_count(self, path: str | None = None) -> int:
        if path is None:
            return len(self.records)
        return sum(1 for record in self.records if record.path == path)


def _handler_for(records: list[ProviderHttpRecord]):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            raw_length = self.headers.get("Content-Length", "0")
            length = int(raw_length) if raw_length.isdigit() else 0
            body = self.rfile.read(length).decode("utf-8")
            records.append(ProviderHttpRecord(path=self.path, body=body))
            if self.path == "/v1/chat/completions":
                self._send_json(_openai_response())
            elif self.path == "/api/generate":
                self._send_json(_local_response())
            elif self.path == "/malformed":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"not-json")
            elif self.path == "/malformed-tool-missing-id":
                self._send_json(_openai_malformed_tool_missing_id())
            elif self.path == "/malformed-tool-bad-arguments":
                self._send_json(_openai_malformed_tool_bad_arguments())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return None

        def _send_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _openai_response() -> dict[str, object]:
    return {
        "id": "chatcmpl_wave16_loopback",
        "choices": [
            {
                "message": {
                    "content": "openai loopback response",
                    "tool_calls": [
                        {
                            "id": "call_weather_live",
                            "function": {
                                "name": "get_weather",
                                "arguments": "{\"location\":\"Seoul\",\"days\":1}",
                            },
                        },
                    ],
                },
            },
        ],
        "usage": {"prompt_tokens": 8, "completion_tokens": 5, "total_tokens": 13},
    }


def _local_response() -> dict[str, object]:
    return {
        "model": "qwen2.5-coder:7b",
        "response": "local llm loopback response",
        "prompt_eval_count": 4,
        "eval_count": 6,
    }


def _openai_malformed_tool_missing_id() -> dict[str, object]:
    return _openai_response_with_tool_call(
        {"function": {"name": "get_weather", "arguments": "{\"location\":\"Seoul\"}"}},
    )


def _openai_malformed_tool_bad_arguments() -> dict[str, object]:
    return _openai_response_with_tool_call(
        {
            "id": "call_bad_arguments",
            "function": {"name": "get_weather", "arguments": "not-json"},
        },
    )


def _openai_response_with_tool_call(tool_call: dict[str, object]) -> dict[str, object]:
    return {
        "id": "chatcmpl_wave16_malformed_tool",
        "choices": [{"message": {"content": "openai loopback response", "tool_calls": [tool_call]}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 5, "total_tokens": 13},
    }
