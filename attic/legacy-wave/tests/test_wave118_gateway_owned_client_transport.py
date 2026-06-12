from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_gateway_owned_client_transport_runtime import (
    LiveGatewayOwnedClientReceipt,
    LiveGatewayOwnedClientRequest,
    LiveGatewayOwnedClientTransportRuntime,
)
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave103_gateway_loopback_transport import _gateway_envelope
from tests.test_wave111_remote_credential_handoff import _gateway_policy
from tests.test_wave112_remote_executor_preflight import _gateway_handoff
from tests.test_wave114_gateway_external_transport import _gateway_preflight


class _FakeGatewayClient:
    def __init__(self, receipt: LiveGatewayOwnedClientReceipt) -> None:
        self.receipt = receipt
        self.requests: list[LiveGatewayOwnedClientRequest] = []

    def deliver(self, request: LiveGatewayOwnedClientRequest) -> LiveGatewayOwnedClientReceipt:
        self.requests.append(request)
        return self.receipt


def test_gateway_owned_client_executes_with_audit_redaction_and_teardown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    client = _FakeGatewayClient(_receipt())

    result = LiveGatewayOwnedClientTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        handoff=_gateway_handoff(),
        gateway_envelope=_gateway_envelope(),
        client=client,
        execution_ref="gateway-owned-client://wave118/slack",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="gateway",
        execution=result,
        audit_ref="live-audit://wave118/gateway-owned-client",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_receipt().response_payload,
        response_ref="live-response://wave118/gateway-owned-client",
    )
    teardown = LiveTransportTeardownRuntime().record(
        home=tmp_path,
        adapter_kind="gateway",
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        execution=result,
        audit=audit,
        teardown_ref=_gateway_policy().teardown_ref or "",
    )

    assert result.decision == "executed"
    assert result.gateway_owned_client is True
    assert result.request_constructed is True
    assert result.header_value_ref_bound is True
    assert result.delivery_attempted is True
    assert result.external_delivery_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert client.requests[0].header_value_ref.startswith("secret-proof://")
    assert "gateway-" + "material-value" not in json.dumps(client.requests[0].to_payload())
    assert audit.decision == "audit_ready"
    assert redaction.decision == "redacted"
    assert teardown.decision == "teardown_recorded"


def test_gateway_owned_client_blocks_handoff_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    handoff = _gateway_handoff().model_copy(update={"policy_id": "wrong-policy"})

    result = LiveGatewayOwnedClientTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        handoff=handoff,
        gateway_envelope=_gateway_envelope(),
        client=_FakeGatewayClient(_receipt()),
        execution_ref="gateway-owned-client://wave118/mismatch",
    )

    assert result.decision == "blocked"
    assert "gateway_handoff_policy_mismatch" in result.blocked_reasons
    assert result.delivery_attempted is False
    assert result.external_delivery_opened is False


def test_gateway_owned_client_blocks_unconfirmed_delivery(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    receipt = _receipt().model_copy(update={"external_delivery_opened": False})

    result = LiveGatewayOwnedClientTransportRuntime().execute(
        policy=_gateway_policy(),
        preflight=_gateway_preflight(),
        handoff=_gateway_handoff(),
        gateway_envelope=_gateway_envelope(),
        client=_FakeGatewayClient(receipt),
        execution_ref="gateway-owned-client://wave118/client-block",
    )

    assert result.decision == "blocked"
    assert "gateway_owned_client_delivery_not_confirmed" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_gateway_owned_client(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    policy = _gateway_policy()
    preflight = _gateway_preflight()
    handoff = _gateway_handoff()
    envelope = _gateway_envelope()
    receipt = _receipt()

    completed = CliRunner().invoke(
        app,
        [
            "live-gateway-owned-client-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--handoff-json",
            handoff.model_dump_json(),
            "--gateway-envelope-json",
            envelope.model_dump_json(),
            "--client-receipt-json",
            receipt.model_dump_json(),
            "--execution-ref",
            "gateway-owned-client://wave118/slack",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_gateway_owned_client_transport(
        policy.to_payload(),
        preflight.to_payload(),
        handoff.to_payload(),
        envelope.to_payload(),
        receipt.model_dump(mode="json"),
        execution_ref="gateway-owned-client://wave118/slack-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["gateway_owned_client"] is True
    assert payload["request_constructed"] is True
    assert payload["external_delivery_opened"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _receipt() -> LiveGatewayOwnedClientReceipt:
    return LiveGatewayOwnedClientReceipt(
        status_code=200,
        latency_ms=49,
        response_payload={"ok": True, "channel": "ops", "debug": "token=xoxb-" + "wave118"},
        network_opened=True,
        non_loopback_network_opened=True,
        external_delivery_opened=True,
        cleanup_receipt="gateway-owned-client-closed",
    )
