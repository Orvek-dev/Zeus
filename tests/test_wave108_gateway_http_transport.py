from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_gateway_http_transport_runtime import LiveGatewayHttpTransportRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer
from tests.test_wave103_gateway_loopback_transport import (
    _gateway_activation,
    _gateway_adapter_plan,
    _gateway_envelope,
)


def test_gateway_http_transport_blocks_non_loopback_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayHttpTransportRuntime().execute(
        activation=_gateway_activation(),
        adapter_plan=_gateway_adapter_plan(),
        gateway_envelope=_gateway_envelope(),
        delivery_endpoint="https://gateway.example.local/deliver",
        transport_kind="local_http",
        execution_ref="gateway-http://wave108/non-loopback",
    )

    assert result.decision == "blocked"
    assert "gateway_http_endpoint_not_loopback" in result.blocked_reasons
    assert result.delivery_attempted is False
    assert result.network_opened is False
    assert result.non_loopback_network_opened is False


def test_gateway_http_transport_executes_loopback_with_audit_and_redaction(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        result = LiveGatewayHttpTransportRuntime().execute(
            activation=_gateway_activation(),
            adapter_plan=_gateway_adapter_plan(),
            gateway_envelope=_gateway_envelope(),
            delivery_endpoint="{0}/v1/chat/completions".format(server.base_url),
            transport_kind="local_http",
            execution_ref="gateway-http://wave108/gateway",
        )
        audit = LiveTransportAuditRuntime().audit(
            adapter_kind="gateway",
            execution=result,
            audit_ref="live-audit://wave108/gateway-http",
        )
        redaction = LiveResponseRedactionRuntime().redact(
            audit=audit,
            response_payload=result.redacted_response or {},
            response_ref="live-response://wave108/gateway-http",
        )
    finally:
        server.shutdown()

    assert result.decision == "executed"
    assert result.local_http_loopback is True
    assert result.delivery_attempted is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.external_delivery_opened is False
    assert result.cleanup_receipt == "gateway-local-http-client-closed"
    assert server.request_count("/v1/chat/completions") == 1
    assert audit.decision == "audit_ready"
    assert redaction.decision == "redacted"
    assert result.live_production_claimed is False
    assert server.shutdown_complete is True


def test_gateway_http_transport_blocks_malformed_response(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        result = LiveGatewayHttpTransportRuntime().execute(
            activation=_gateway_activation(),
            adapter_plan=_gateway_adapter_plan(),
            gateway_envelope=_gateway_envelope(),
            delivery_endpoint="{0}/malformed".format(server.base_url),
            transport_kind="local_http",
            execution_ref="gateway-http://wave108/malformed",
        )
    finally:
        server.shutdown()

    assert result.decision == "blocked"
    assert "gateway_http_response_not_json_object" in result.blocked_reasons
    assert result.network_opened is True
    assert result.handler_executed is False
    assert server.request_count("/malformed") == 1


def test_cli_and_python_library_gateway_http_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        endpoint = "{0}/v1/chat/completions".format(server.base_url)
        activation = _gateway_activation()
        adapter_plan = _gateway_adapter_plan()
        envelope = _gateway_envelope()
        completed = CliRunner().invoke(
            app,
            [
                "live-gateway-http-transport",
                "--activation-json",
                activation.model_dump_json(),
                "--adapter-plan-json",
                adapter_plan.model_dump_json(),
                "--gateway-envelope-json",
                envelope.model_dump_json(),
                "--delivery-endpoint",
                endpoint,
                "--transport-kind",
                "local_http",
                "--execution-ref",
                "gateway-http://wave108/gateway",
                "--json",
            ],
        )
        library_payload = ZeusAgent().live_gateway_http_transport(
            activation.to_payload(),
            adapter_plan=adapter_plan.to_payload(),
            gateway_envelope=envelope.to_payload(),
            delivery_endpoint=endpoint,
            transport_kind="local_http",
            execution_ref="gateway-http://wave108/gateway-library",
        )
    finally:
        server.shutdown()

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["external_delivery_opened"] is False
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"
    assert server.request_count("/v1/chat/completions") == 2
