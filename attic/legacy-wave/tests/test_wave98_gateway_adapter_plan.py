from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterRuntime
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryRuntime
from tests.test_wave92_gateway_delivery_envelope import _gateway_transport_lease, _secret_material
from tests.test_wave94_execution_authorization import _operator_proof


def test_gateway_adapter_plan_blocks_without_release(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayAdapterRuntime().plan(
        release=None,
        gateway_envelope=_gateway_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave98-gateway-adapter-1",
    )

    assert result.decision == "blocked"
    assert "executor_release_required" in result.blocked_reasons
    assert result.adapter_plan_ready is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_gateway_adapter_plan_prepares_dry_run_without_delivery(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayAdapterRuntime().plan(
        release=_gateway_release(),
        gateway_envelope=_gateway_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave98-gateway-adapter-1",
    )

    assert result.decision == "planned"
    assert result.adapter_plan_ready is True
    assert result.release_bound is True
    assert result.gateway_envelope_bound is True
    assert result.live_transport_requested is False
    assert result.delivery_attempted is False
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_transport_enabled is False
    assert result.live_production_claimed is False


def test_gateway_adapter_plan_blocks_live_delivery_until_executor_exists(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")

    result = LiveGatewayAdapterRuntime().plan(
        release=_gateway_release(),
        gateway_envelope=_gateway_envelope(),
        transport_mode="live",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave98-gateway-adapter-1",
    )

    assert result.decision == "blocked"
    assert "gateway_live_transport_not_implemented" in result.blocked_reasons
    assert result.live_transport_requested is True
    assert result.delivery_attempted is False
    assert result.network_opened is False


def test_cli_and_python_library_gateway_adapter_plan(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    release = _gateway_release()
    envelope = _gateway_envelope()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-gateway-adapter-plan",
            "--release-json",
            release.model_dump_json(),
            "--gateway-envelope-json",
            envelope.model_dump_json(),
            "--transport-mode",
            "dry_run",
            "--timeout-ms",
            "1500",
            "--retry-attempts",
            "1",
            "--idempotency-key",
            "wave98-gateway-adapter-1",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "planned"
    assert payload["external_delivery_opened"] is False

    library_payload = ZeusAgent().live_gateway_adapter_plan(
        release.to_payload(),
        gateway_envelope=envelope.to_payload(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave98-gateway-adapter-1",
    )
    assert library_payload["decision"] == "planned"
    assert library_payload["delivery_attempted"] is False


def _gateway_envelope():
    return LiveGatewayDeliveryRuntime().prepare(
        transport_lease=_gateway_transport_lease(),
        secret_material=_secret_material(),
        adapter_id="slack",
        target="slack://ops",
        message="status update",
        idempotency_key="wave92-delivery-1",
    )


def _gateway_release():
    risks = ("network", "credential_material_access", "external_delivery")
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="gateway",
        envelope=_gateway_envelope().to_payload(),
        operator_proof=_operator_proof(reviewed_risks=risks),
        required_risks=risks,
    )
    return LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="gateway",
        release_ref="executor-release://wave98/gateway",
        idempotency_key="wave98-gateway-release-1",
    )
