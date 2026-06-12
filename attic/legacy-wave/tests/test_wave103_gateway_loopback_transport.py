from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryRuntime
from zeus_agent.live_gateway_loopback_transport_runtime import LiveGatewayLoopbackTransportRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from tests.test_wave100_live_transport_opt_in import _gateway_adapter_plan
from tests.test_wave101_transport_activation_plan import _gateway_opt_in
from tests.test_wave92_gateway_delivery_envelope import _gateway_transport_lease, _secret_material
from tests.test_wave98_gateway_adapter_plan import _gateway_envelope


def test_gateway_loopback_transport_blocks_without_activation(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayLoopbackTransportRuntime().execute(
        activation=None,
        adapter_plan=_gateway_adapter_plan(),
        gateway_envelope=_gateway_envelope(),
        transport_kind="loopback_delivery",
        execution_ref="gateway-loopback://wave103/gateway",
    )

    assert result.decision == "blocked"
    assert "transport_activation_required" in result.blocked_reasons
    assert result.delivery_attempted is False
    assert result.live_transport_enabled is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_gateway_loopback_transport_executes_without_external_delivery(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayLoopbackTransportRuntime().execute(
        activation=_gateway_activation(),
        adapter_plan=_gateway_adapter_plan(),
        gateway_envelope=_gateway_envelope(),
        transport_kind="loopback_delivery",
        execution_ref="gateway-loopback://wave103/gateway",
    )

    assert result.decision == "executed"
    assert result.transport_activation_bound is True
    assert result.adapter_plan_bound is True
    assert result.gateway_envelope_bound is True
    assert result.loopback_transport is True
    assert result.delivery_attempted is True
    assert result.handler_executed is True
    assert result.live_transport_enabled is True
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert result.cleanup_receipt == "gateway-loopback-no-delivery"


def test_gateway_loopback_transport_blocks_external_delivery(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayLoopbackTransportRuntime().execute(
        activation=_gateway_activation(),
        adapter_plan=_gateway_adapter_plan(),
        gateway_envelope=_gateway_envelope(),
        transport_kind="external_delivery",
        execution_ref="gateway-loopback://wave103/gateway",
    )

    assert result.decision == "blocked"
    assert "gateway_external_delivery_not_implemented" in result.blocked_reasons
    assert result.delivery_attempted is False
    assert result.external_delivery_opened is False


def test_gateway_loopback_transport_blocks_envelope_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayLoopbackTransportRuntime().execute(
        activation=_gateway_activation(),
        adapter_plan=_gateway_adapter_plan(),
        gateway_envelope=_different_gateway_envelope(),
        transport_kind="loopback_delivery",
        execution_ref="gateway-loopback://wave103/gateway",
    )

    assert result.decision == "blocked"
    assert "adapter_gateway_envelope_mismatch" in result.blocked_reasons
    assert result.delivery_attempted is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_gateway_loopback_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    activation = _gateway_activation()
    adapter_plan = _gateway_adapter_plan()
    envelope = _gateway_envelope()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-gateway-loopback-transport",
            "--activation-json",
            activation.model_dump_json(),
            "--adapter-plan-json",
            adapter_plan.model_dump_json(),
            "--gateway-envelope-json",
            envelope.model_dump_json(),
            "--transport-kind",
            "loopback_delivery",
            "--execution-ref",
            "gateway-loopback://wave103/gateway",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["external_delivery_opened"] is False

    library_payload = ZeusAgent().live_gateway_loopback_transport(
        activation.to_payload(),
        adapter_plan=adapter_plan.to_payload(),
        gateway_envelope=envelope.to_payload(),
        transport_kind="loopback_delivery",
        execution_ref="gateway-loopback://wave103/gateway",
    )
    assert library_payload["decision"] == "executed"
    assert library_payload["network_opened"] is False


def _gateway_activation():
    return LiveTransportActivationRuntime().plan(
        opt_in=_gateway_opt_in(),
        adapter_kind="gateway",
        adapter_plan=_gateway_adapter_plan(),
        activation_ref="live-activation://wave103/gateway",
    )


def _different_gateway_envelope():
    return LiveGatewayDeliveryRuntime().prepare(
        transport_lease=_gateway_transport_lease(),
        secret_material=_secret_material(),
        adapter_id="slack",
        target="slack://ops",
        message="different status update",
        idempotency_key="wave103-different-delivery",
    )
