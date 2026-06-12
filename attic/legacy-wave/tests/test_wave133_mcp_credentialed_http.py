from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_mcp_credentialed_http_runtime import LiveMcpCredentialedHttpRuntime
from zeus_agent.live_mcp_request_body_runtime import LiveMcpRequestBodyRuntime
from tests.test_wave109_mcp_http_transport import _mcp_envelope
from tests.test_wave127_sealed_credential_release import _mcp_injection


def test_mcp_credentialed_http_executes_loopback_with_sealed_header(monkeypatch, tmp_path: Path) -> None:
    material = "mcp-" + "material-value"
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", material)
    server = _CredentialedMcpServer()
    server.start()
    try:
        injection, secret_material = _mcp_injection(tmp_path)
        envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")
        body = _mcp_body(envelope, {"query": "Zeus"})

        result = LiveMcpCredentialedHttpRuntime().execute(
            injection=injection,
            secret_material=secret_material,
            mcp_envelope=envelope,
            request_body=body,
            transport_endpoint="{0}/rpc".format(server.base_url),
            timeout_ms=1500,
            release_ref="sealed-credential://wave133/mcp",
            execution_ref="mcp-credentialed-http://wave133/mcp",
        )
    finally:
        server.shutdown()

    payload = json.dumps(result.to_payload())
    assert result.decision == "executed"
    assert result.mcp_credentialed_http is True
    assert result.sealed_credential_bound is True
    assert result.mcp_request_body_bound is True
    assert result.local_http_loopback is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.tool_invoked is True
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.credential_material_accessed is True
    assert result.material_released_to_consumer is True
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert result.status_code == 200
    assert material not in payload
    assert _header_value(server.records[0].headers, "X-API-Key") == material
    assert json.loads(server.records[0].body)["params"]["arguments"]["query"] == "Zeus"
    assert server.shutdown_complete is True


def test_mcp_credentialed_http_blocks_non_loopback_before_secret_release(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    injection, secret_material = _mcp_injection(tmp_path)
    envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")
    body = _mcp_body(envelope, {"query": "Zeus"})

    result = LiveMcpCredentialedHttpRuntime().execute(
        injection=injection,
        secret_material=secret_material,
        mcp_envelope=envelope,
        request_body=body,
        transport_endpoint="https://mcp.github.local/rpc",
        timeout_ms=1500,
        release_ref="sealed-credential://wave133/non-loopback",
        execution_ref="mcp-credentialed-http://wave133/non-loopback",
    )

    assert result.decision == "blocked"
    assert "mcp_credentialed_http_endpoint_not_loopback" in result.blocked_reasons
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.material_released_to_consumer is False


def test_mcp_credentialed_http_blocks_body_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    injection, secret_material = _mcp_injection(tmp_path)
    envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")
    body = _mcp_body(envelope, {"query": "Zeus"}).model_copy(update={"request_envelope_id": "wrong-envelope"})

    result = LiveMcpCredentialedHttpRuntime().execute(
        injection=injection,
        secret_material=secret_material,
        mcp_envelope=envelope,
        request_body=body,
        transport_endpoint="http://127.0.0.1:9/rpc",
        timeout_ms=1500,
        release_ref="sealed-credential://wave133/body-mismatch",
        execution_ref="mcp-credentialed-http://wave133/body-mismatch",
    )

    assert result.decision == "blocked"
    assert "mcp_request_body_envelope_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_cli_and_python_library_mcp_credentialed_http(monkeypatch, tmp_path: Path) -> None:
    material = "mcp-" + "material-value"
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", material)
    server = _CredentialedMcpServer()
    server.start()
    try:
        injection, secret_material = _mcp_injection(tmp_path)
        envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")
        body = _mcp_body(envelope, {"query": "Zeus"})

        completed = CliRunner().invoke(
            app,
            [
                "live-mcp-credentialed-http",
                "--injection-json",
                injection.model_dump_json(),
                "--secret-material-json",
                secret_material.model_dump_json(),
                "--mcp-envelope-json",
                envelope.model_dump_json(),
                "--request-body-json",
                body.model_dump_json(),
                "--transport-endpoint",
                "{0}/rpc".format(server.base_url),
                "--timeout-ms",
                "1500",
                "--release-ref",
                "sealed-credential://wave133/mcp-cli",
                "--execution-ref",
                "mcp-credentialed-http://wave133/mcp-cli",
                "--json",
            ],
        )
        library_payload = ZeusAgent(home=tmp_path).live_mcp_credentialed_http(
            injection.to_payload(),
            secret_material.to_payload(),
            envelope.to_payload(),
            body.to_payload(),
            transport_endpoint="{0}/rpc".format(server.base_url),
            timeout_ms=1500,
            release_ref="sealed-credential://wave133/mcp-library",
            execution_ref="mcp-credentialed-http://wave133/mcp-library",
        )
    finally:
        server.shutdown()

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["server_started"] is False
    assert payload["raw_secret_returned"] is False
    assert material not in completed.stdout
    assert library_payload["decision"] == "executed"
    assert material not in json.dumps(library_payload)
    assert server.request_count("/rpc") == 2


def _mcp_body(envelope, arguments: dict[str, object]):
    return LiveMcpRequestBodyRuntime().materialize(
        mcp_envelope=envelope,
        arguments=arguments,
        body_ref="mcp-body://wave133/mcp",
    )


def _header_value(headers: dict[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    raise KeyError(name)


@dataclass(frozen=True)
class _McpRecord:
    path: str
    headers: dict[str, str]
    body: str


class _CredentialedMcpServer:
    def __init__(self) -> None:
        self.records: list[_McpRecord] = []
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

    def request_count(self, path: str) -> int:
        return sum(1 for record in self.records if record.path == path)


def _handler_for(records: list[_McpRecord]):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            raw_length = self.headers.get("Content-Length", "0")
            length = int(raw_length) if raw_length.isdigit() else 0
            body = self.rfile.read(length).decode("utf-8")
            records.append(_McpRecord(path=self.path, headers=dict(self.headers), body=body))
            response_body = json.dumps({"result": {"repositories": ["Orvek-dev/Zeus"]}}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    return Handler
