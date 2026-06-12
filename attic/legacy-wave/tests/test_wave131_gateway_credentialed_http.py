from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_gateway_credentialed_http_runtime import LiveGatewayCredentialedHttpRuntime
from zeus_agent.live_gateway_delivery_body_runtime import LiveGatewayDeliveryBodyRuntime
from tests.test_wave114_gateway_external_transport import _gateway_preflight
from tests.test_wave123_gateway_delivery_adapter import _gateway_claim
from tests.test_wave92_gateway_delivery_envelope import _secret_material as _gateway_secret_material
from tests.test_wave98_gateway_adapter_plan import _gateway_envelope
from tests.test_wave111_remote_credential_handoff import _gateway_policy
from tests.test_wave112_remote_executor_preflight import _gateway_handoff


def test_gateway_credentialed_http_executes_loopback_with_sealed_header(monkeypatch, tmp_path: Path) -> None:
    material = "gateway-" + "material-value"
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", material)
    server = _CredentialedGatewayServer()
    server.start()
    try:
        injection, secret_material = _gateway_injection(tmp_path)
        envelope = _gateway_envelope()
        body = _delivery_body(envelope, "status update")

        result = LiveGatewayCredentialedHttpRuntime().execute(
            injection=injection,
            secret_material=secret_material,
            gateway_envelope=envelope,
            delivery_body=body,
            delivery_endpoint="{0}/deliver".format(server.base_url),
            timeout_ms=1500,
            release_ref="sealed-credential://wave131/gateway",
            execution_ref="gateway-credentialed-http://wave131/gateway",
        )
    finally:
        server.shutdown()

    payload = json.dumps(result.to_payload())
    assert result.decision == "executed"
    assert result.gateway_credentialed_http is True
    assert result.sealed_credential_bound is True
    assert result.gateway_delivery_body_bound is True
    assert result.local_http_loopback is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.external_delivery_opened is False
    assert result.credential_material_accessed is True
    assert result.material_released_to_consumer is True
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert result.status_code == 200
    assert result.redacted_response["answer"] == "credentialed gateway response"
    assert material not in payload
    assert server.records[0].headers["Authorization"] == "Bearer {0}".format(material)
    assert json.loads(server.records[0].body)["message"] == "status update"
    assert server.shutdown_complete is True


def test_gateway_credentialed_http_blocks_non_loopback_before_secret_release(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    injection, secret_material = _gateway_injection(tmp_path)
    envelope = _gateway_envelope()
    body = _delivery_body(envelope, "status update")

    result = LiveGatewayCredentialedHttpRuntime().execute(
        injection=injection,
        secret_material=secret_material,
        gateway_envelope=envelope,
        delivery_body=body,
        delivery_endpoint="https://gateway.example.local/deliver",
        timeout_ms=1500,
        release_ref="sealed-credential://wave131/non-loopback",
        execution_ref="gateway-credentialed-http://wave131/non-loopback",
    )

    assert result.decision == "blocked"
    assert "gateway_credentialed_http_endpoint_not_loopback" in result.blocked_reasons
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.material_released_to_consumer is False


def test_gateway_credentialed_http_blocks_body_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    injection, secret_material = _gateway_injection(tmp_path)
    envelope = _gateway_envelope()
    body = _delivery_body(envelope, "status update").model_copy(update={"delivery_envelope_id": "wrong-envelope"})

    result = LiveGatewayCredentialedHttpRuntime().execute(
        injection=injection,
        secret_material=secret_material,
        gateway_envelope=envelope,
        delivery_body=body,
        delivery_endpoint="http://127.0.0.1:9/deliver",
        timeout_ms=1500,
        release_ref="sealed-credential://wave131/body-mismatch",
        execution_ref="gateway-credentialed-http://wave131/body-mismatch",
    )

    assert result.decision == "blocked"
    assert "gateway_delivery_body_envelope_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_cli_and_python_library_gateway_credentialed_http(monkeypatch, tmp_path: Path) -> None:
    material = "gateway-" + "material-value"
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", material)
    server = _CredentialedGatewayServer()
    server.start()
    try:
        injection, secret_material = _gateway_injection(tmp_path)
        envelope = _gateway_envelope()
        body = _delivery_body(envelope, "status update")

        completed = CliRunner().invoke(
            app,
            [
                "live-gateway-credentialed-http",
                "--injection-json",
                injection.model_dump_json(),
                "--secret-material-json",
                secret_material.model_dump_json(),
                "--gateway-envelope-json",
                envelope.model_dump_json(),
                "--delivery-body-json",
                body.model_dump_json(),
                "--delivery-endpoint",
                "{0}/deliver".format(server.base_url),
                "--timeout-ms",
                "1500",
                "--release-ref",
                "sealed-credential://wave131/gateway-cli",
                "--execution-ref",
                "gateway-credentialed-http://wave131/gateway-cli",
                "--json",
            ],
        )
        library_payload = ZeusAgent(home=tmp_path).live_gateway_credentialed_http(
            injection.to_payload(),
            secret_material.to_payload(),
            envelope.to_payload(),
            body.to_payload(),
            delivery_endpoint="{0}/deliver".format(server.base_url),
            timeout_ms=1500,
            release_ref="sealed-credential://wave131/gateway-library",
            execution_ref="gateway-credentialed-http://wave131/gateway-library",
        )
    finally:
        server.shutdown()

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["external_delivery_opened"] is False
    assert payload["raw_secret_returned"] is False
    assert material not in completed.stdout
    assert library_payload["decision"] == "executed"
    assert material not in json.dumps(library_payload)
    assert server.request_count("/deliver") == 2


def _gateway_injection(tmp_path: Path):
    secret_material = _gateway_secret_material()
    return (
        LiveCredentialInjectionRuntime().prepare(
            adapter_kind="gateway",
            claim=_gateway_claim(tmp_path),
            policy=_gateway_policy(),
            preflight=_gateway_preflight(),
            handoff=_gateway_handoff(),
            secret_material=secret_material,
            injection_ref="credential-injection://wave131/gateway",
        ),
        secret_material,
    )


def _delivery_body(envelope, message: str):
    return LiveGatewayDeliveryBodyRuntime().materialize(
        gateway_envelope=envelope,
        message=message,
        body_ref="gateway-body://wave131/gateway",
    )


@dataclass(frozen=True)
class _GatewayRecord:
    path: str
    headers: dict[str, str]
    body: str


class _CredentialedGatewayServer:
    def __init__(self) -> None:
        self.records: list[_GatewayRecord] = []
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


def _handler_for(records: list[_GatewayRecord]):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            raw_length = self.headers.get("Content-Length", "0")
            length = int(raw_length) if raw_length.isdigit() else 0
            body = self.rfile.read(length).decode("utf-8")
            records.append(_GatewayRecord(path=self.path, headers=dict(self.headers), body=body))
            response_body = json.dumps({"answer": "credentialed gateway response"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    return Handler
