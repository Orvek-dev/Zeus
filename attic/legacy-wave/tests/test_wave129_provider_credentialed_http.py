from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_credentialed_http_runtime import LiveProviderCredentialedHttpRuntime
from zeus_agent.live_provider_request_body_runtime import LiveProviderRequestBodyRuntime
from tests.test_wave113_provider_external_transport import _provider_request
from tests.test_wave127_sealed_credential_release import _provider_injection


def test_provider_credentialed_http_executes_loopback_with_sealed_header(monkeypatch, tmp_path: Path) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", material)
    server = _CredentialedProviderServer()
    server.start()
    try:
        injection, secret_material = _provider_injection(tmp_path)
        envelope = _provider_request()
        body = _request_body(envelope, "summarize local transport state")

        result = LiveProviderCredentialedHttpRuntime().execute(
            injection=injection,
            secret_material=secret_material,
            provider_envelope=envelope,
            request_body=body,
            transport_endpoint="{0}/v1/chat/completions".format(server.base_url),
            timeout_ms=1500,
            release_ref="sealed-credential://wave129/provider",
            execution_ref="provider-credentialed-http://wave129/provider",
        )
    finally:
        server.shutdown()

    payload = json.dumps(result.to_payload())
    assert result.decision == "executed"
    assert result.provider_credentialed_http is True
    assert result.sealed_credential_bound is True
    assert result.provider_request_body_bound is True
    assert result.local_http_loopback is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.credential_material_accessed is True
    assert result.material_released_to_consumer is True
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert result.status_code == 200
    assert result.redacted_response["answer"] == "credentialed provider response"
    assert "s" + "k-wave129" not in json.dumps(result.redacted_response)
    assert material not in payload
    assert server.records[0].headers["Authorization"] == "Bearer {0}".format(material)
    assert json.loads(server.records[0].body)["messages"][0]["content"] == "summarize local transport state"
    assert server.shutdown_complete is True


def test_provider_credentialed_http_blocks_non_loopback_transport_before_secret_release(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    injection, secret_material = _provider_injection(tmp_path)
    envelope = _provider_request()
    body = _request_body(envelope, "summarize local transport state")

    result = LiveProviderCredentialedHttpRuntime().execute(
        injection=injection,
        secret_material=secret_material,
        provider_envelope=envelope,
        request_body=body,
        transport_endpoint="https://api.openai.local/v1/chat/completions",
        timeout_ms=1500,
        release_ref="sealed-credential://wave129/non-loopback",
        execution_ref="provider-credentialed-http://wave129/non-loopback",
    )

    assert result.decision == "blocked"
    assert "provider_credentialed_http_endpoint_not_loopback" in result.blocked_reasons
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.material_released_to_consumer is False


def test_provider_credentialed_http_blocks_request_body_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    injection, secret_material = _provider_injection(tmp_path)
    envelope = _provider_request()
    body = _request_body(envelope, "summarize local transport state").model_copy(
        update={"request_envelope_id": "wrong-request-envelope"}
    )

    result = LiveProviderCredentialedHttpRuntime().execute(
        injection=injection,
        secret_material=secret_material,
        provider_envelope=envelope,
        request_body=body,
        transport_endpoint="http://127.0.0.1:9/v1/chat/completions",
        timeout_ms=1500,
        release_ref="sealed-credential://wave129/body-mismatch",
        execution_ref="provider-credentialed-http://wave129/body-mismatch",
    )

    assert result.decision == "blocked"
    assert "provider_request_body_envelope_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_cli_and_python_library_provider_credentialed_http(monkeypatch, tmp_path: Path) -> None:
    material = "provider-" + "material-value"
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", material)
    server = _CredentialedProviderServer()
    server.start()
    try:
        injection, secret_material = _provider_injection(tmp_path)
        envelope = _provider_request()
        body = _request_body(envelope, "summarize local transport state")

        completed = CliRunner().invoke(
            app,
            [
                "live-provider-credentialed-http",
                "--injection-json",
                injection.model_dump_json(),
                "--secret-material-json",
                secret_material.model_dump_json(),
                "--provider-envelope-json",
                envelope.model_dump_json(),
                "--request-body-json",
                body.model_dump_json(),
                "--transport-endpoint",
                "{0}/v1/chat/completions".format(server.base_url),
                "--timeout-ms",
                "1500",
                "--release-ref",
                "sealed-credential://wave129/provider-cli",
                "--execution-ref",
                "provider-credentialed-http://wave129/provider-cli",
                "--json",
            ],
        )
        library_payload = ZeusAgent(home=tmp_path).live_provider_credentialed_http(
            injection.to_payload(),
            secret_material.to_payload(),
            envelope.to_payload(),
            body.to_payload(),
            transport_endpoint="{0}/v1/chat/completions".format(server.base_url),
            timeout_ms=1500,
            release_ref="sealed-credential://wave129/provider-library",
            execution_ref="provider-credentialed-http://wave129/provider-library",
        )
    finally:
        server.shutdown()

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["raw_secret_returned"] is False
    assert material not in completed.stdout
    assert library_payload["decision"] == "executed"
    assert material not in json.dumps(library_payload)
    assert server.request_count("/v1/chat/completions") == 2


def _request_body(envelope, message: str):
    return LiveProviderRequestBodyRuntime().materialize(
        provider_envelope=envelope,
        message=message,
        body_ref="provider-body://wave129/provider",
    )


@dataclass(frozen=True)
class _ProviderRecord:
    path: str
    headers: dict[str, str]
    body: str


class _CredentialedProviderServer:
    def __init__(self) -> None:
        self.records: list[_ProviderRecord] = []
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


def _handler_for(records: list[_ProviderRecord]):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            raw_length = self.headers.get("Content-Length", "0")
            length = int(raw_length) if raw_length.isdigit() else 0
            body = self.rfile.read(length).decode("utf-8")
            records.append(_ProviderRecord(path=self.path, headers=dict(self.headers), body=body))
            payload = {
                "answer": "credentialed provider response",
                "debug": "token=" + "s" + "k-wave129",
            }
            response_body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    return Handler
