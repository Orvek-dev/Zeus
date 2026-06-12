from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from tests.test_wave88_live_gateway_execution import _gateway_readiness
from tests.test_wave89_live_transport_lease import _gateway_lease, _now


def test_gateway_delivery_envelope_blocks_without_transport_lease() -> None:
    result = LiveGatewayDeliveryRuntime().prepare(
        transport_lease=None,
        secret_material=None,
        adapter_id="slack",
        target="slack://ops",
        message="status update",
        idempotency_key="wave92-delivery-1",
    )

    assert result.decision == "blocked"
    assert "transport_lease_required" in result.blocked_reasons
    assert result.delivery_prepared is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_gateway_delivery_envelope_prepares_without_external_delivery(monkeypatch) -> None:
    material = "gateway-" + "material-value"
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", material)

    result = LiveGatewayDeliveryRuntime().prepare(
        transport_lease=_gateway_transport_lease(),
        secret_material=_secret_material(),
        adapter_id="slack",
        target="slack://ops",
        message="status update",
        idempotency_key="wave92-delivery-1",
    )

    payload = result.to_payload()
    assert result.decision == "prepared"
    assert result.delivery_prepared is True
    assert result.secret_material_verified is True
    assert result.delivery_target_allowlisted is True
    assert result.delivery_attempted is False
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert material not in json.dumps(payload)


def test_gateway_delivery_envelope_blocks_target_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayDeliveryRuntime().prepare(
        transport_lease=_gateway_transport_lease(),
        secret_material=_secret_material(),
        adapter_id="slack",
        target="discord://ops",
        message="status update",
        idempotency_key="wave92-delivery-1",
    )

    assert result.decision == "blocked"
    assert "delivery_target_not_allowlisted" in result.blocked_reasons
    assert result.delivery_prepared is False
    assert result.external_delivery_opened is False


def test_cli_and_python_library_gateway_delivery_envelope(monkeypatch) -> None:
    material = "gateway-" + "material-value"
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", material)
    transport_lease = _gateway_transport_lease()
    secret_material = _secret_material()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-gateway-delivery-envelope",
            "--transport-lease-json",
            transport_lease.model_dump_json(),
            "--secret-material-json",
            secret_material.model_dump_json(),
            "--adapter-id",
            "slack",
            "--target",
            "slack://ops",
            "--message",
            "status update",
            "--idempotency-key",
            "wave92-delivery-1",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "prepared"
    assert payload["external_delivery_opened"] is False
    assert material not in completed.stdout

    library_payload = ZeusAgent().live_gateway_delivery_envelope(
        transport_lease.to_payload(),
        secret_material.to_payload(),
        adapter_id="slack",
        target="slack://ops",
        message="status update",
        idempotency_key="wave92-delivery-1",
    )
    assert library_payload["decision"] == "prepared"
    assert library_payload["delivery_attempted"] is False


def _gateway_transport_lease():
    return LiveTransportLeaseRuntime().bind(
        readiness=_gateway_readiness(),
        lease=_gateway_lease(),
        runtime_kind="gateway",
        capability_id="gateway.slack.dispatch",
        credential_scope="external.gateway.readonly",
        network_host="gateway.local",
        budget_required=1,
        evidence_target="mneme.wave89.live_transport_lease",
        now=_now(),
    )


def _secret_material():
    return LiveSecretMaterialRuntime().check(
        transport_lease=_gateway_transport_lease(),
        secret_ref="env://ZEUS_W92_GATEWAY_TOKEN",
        allow_material_access=True,
    )
