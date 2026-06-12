from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_loopback_transport_runtime import LiveProviderLoopbackTransportRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from tests.test_wave100_live_transport_opt_in import _provider_adapter_plan
from tests.test_wave101_transport_activation_plan import _provider_opt_in
from tests.test_wave91_provider_request_envelope import _provider_transport_lease, _secret_material
from tests.test_wave97_provider_adapter_plan import _provider_envelope


def test_provider_loopback_transport_blocks_without_activation(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderLoopbackTransportRuntime().execute(
        activation=None,
        adapter_plan=_provider_adapter_plan(),
        provider_envelope=_provider_envelope(),
        transport_kind="loopback_http",
        execution_ref="provider-loopback://wave102/provider",
    )

    assert result.decision == "blocked"
    assert "transport_activation_required" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_provider_loopback_transport_executes_without_external_network(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderLoopbackTransportRuntime().execute(
        activation=_provider_activation(),
        adapter_plan=_provider_adapter_plan(),
        provider_envelope=_provider_envelope(),
        transport_kind="loopback_http",
        execution_ref="provider-loopback://wave102/provider",
    )

    assert result.decision == "executed"
    assert result.transport_activation_bound is True
    assert result.adapter_plan_bound is True
    assert result.provider_envelope_bound is True
    assert result.loopback_transport is True
    assert result.provider_invoked is True
    assert result.handler_executed is True
    assert result.live_transport_enabled is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert result.cleanup_receipt == "provider-loopback-no-network"


def test_provider_loopback_transport_blocks_external_http(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderLoopbackTransportRuntime().execute(
        activation=_provider_activation(),
        adapter_plan=_provider_adapter_plan(),
        provider_envelope=_provider_envelope(),
        transport_kind="external_http",
        execution_ref="provider-loopback://wave102/provider",
    )

    assert result.decision == "blocked"
    assert "provider_external_http_not_implemented" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False


def test_provider_loopback_transport_blocks_envelope_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderLoopbackTransportRuntime().execute(
        activation=_provider_activation(),
        adapter_plan=_provider_adapter_plan(),
        provider_envelope=_different_provider_envelope(),
        transport_kind="loopback_http",
        execution_ref="provider-loopback://wave102/provider",
    )

    assert result.decision == "blocked"
    assert "adapter_provider_envelope_mismatch" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_provider_loopback_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    activation = _provider_activation()
    adapter_plan = _provider_adapter_plan()
    envelope = _provider_envelope()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-provider-loopback-transport",
            "--activation-json",
            activation.model_dump_json(),
            "--adapter-plan-json",
            adapter_plan.model_dump_json(),
            "--provider-envelope-json",
            envelope.model_dump_json(),
            "--transport-kind",
            "loopback_http",
            "--execution-ref",
            "provider-loopback://wave102/provider",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is False

    library_payload = ZeusAgent().live_provider_loopback_transport(
        activation.to_payload(),
        adapter_plan=adapter_plan.to_payload(),
        provider_envelope=envelope.to_payload(),
        transport_kind="loopback_http",
        execution_ref="provider-loopback://wave102/provider",
    )
    assert library_payload["decision"] == "executed"
    assert library_payload["live_production_claimed"] is False


def _provider_activation():
    return LiveTransportActivationRuntime().plan(
        opt_in=_provider_opt_in(),
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(),
        activation_ref="live-activation://wave102/provider",
    )


def _different_provider_envelope():
    return LiveProviderRequestRuntime().prepare(
        transport_lease=_provider_transport_lease(),
        secret_material=_secret_material(),
        provider_kind="openai_compatible",
        model_id="gpt-test",
        endpoint="https://api.openai.local/v1/chat/completions",
        message="summarize different local state",
    )
