from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from tests.test_wave100_live_transport_opt_in import (
    _gateway_adapter_plan,
    _mcp_adapter_plan,
    _proof,
    _provider_adapter_plan,
)
from tests.test_wave97_provider_adapter_plan import _provider_envelope, _release as _provider_release


def test_transport_activation_blocks_without_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveTransportActivationRuntime().plan(
        opt_in=None,
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(),
        activation_ref="live-activation://wave101/provider",
    )

    assert result.decision == "blocked"
    assert "live_transport_opt_in_required" in result.blocked_reasons
    assert result.transport_activation_ready is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_transport_activation_accepts_opted_in_adapter_plans_for_all_surfaces(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    provider = LiveTransportActivationRuntime().plan(
        opt_in=_provider_opt_in(),
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(),
        activation_ref="live-activation://wave101/provider",
    )
    gateway = LiveTransportActivationRuntime().plan(
        opt_in=_gateway_opt_in(),
        adapter_kind="gateway",
        adapter_plan=_gateway_adapter_plan(),
        activation_ref="live-activation://wave101/gateway",
    )
    mcp = LiveTransportActivationRuntime().plan(
        opt_in=_mcp_opt_in(),
        adapter_kind="mcp",
        adapter_plan=_mcp_adapter_plan(),
        activation_ref="live-activation://wave101/mcp",
    )

    for result in (provider, gateway, mcp):
        assert result.decision == "activation_ready"
        assert result.transport_activation_ready is True
        assert result.opt_in_bound is True
        assert result.adapter_plan_bound is True
        assert result.live_transport_authorized is True
        assert result.live_transport_enabled is False
        assert result.network_opened is False
        assert result.credential_material_accessed is False
        assert result.live_production_claimed is False


def test_transport_activation_blocks_adapter_plan_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveTransportActivationRuntime().plan(
        opt_in=_provider_opt_in(),
        adapter_kind="provider",
        adapter_plan=_different_provider_adapter_plan(),
        activation_ref="live-activation://wave101/provider",
    )

    assert result.decision == "blocked"
    assert "opt_in_adapter_plan_mismatch" in result.blocked_reasons
    assert result.transport_activation_ready is False
    assert result.live_transport_authorized is False


def test_cli_and_python_library_transport_activation(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    opt_in = _provider_opt_in()
    adapter_plan = _provider_adapter_plan()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-transport-activation-plan",
            "--opt-in-json",
            opt_in.model_dump_json(),
            "--adapter-kind",
            "provider",
            "--adapter-plan-json",
            adapter_plan.model_dump_json(),
            "--activation-ref",
            "live-activation://wave101/provider",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "activation_ready"
    assert payload["live_transport_enabled"] is False

    library_payload = ZeusAgent().live_transport_activation_plan(
        opt_in.to_payload(),
        adapter_kind="provider",
        adapter_plan=adapter_plan.to_payload(),
        activation_ref="live-activation://wave101/provider",
    )
    assert library_payload["decision"] == "activation_ready"
    assert library_payload["network_opened"] is False


def _provider_opt_in():
    return LiveTransportOptInRuntime().record(
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(),
        operator_proof=_proof(("network", "credential_material_access", "external_provider_inference", "live_transport")),
        opt_in_ref="live-opt-in://wave101/provider",
        requested_transport_mode="live",
    )


def _gateway_opt_in():
    return LiveTransportOptInRuntime().record(
        adapter_kind="gateway",
        adapter_plan=_gateway_adapter_plan(),
        operator_proof=_proof(("network", "credential_material_access", "external_delivery", "live_transport")),
        opt_in_ref="live-opt-in://wave101/gateway",
        requested_transport_mode="live",
    )


def _mcp_opt_in():
    return LiveTransportOptInRuntime().record(
        adapter_kind="mcp",
        adapter_plan=_mcp_adapter_plan(),
        operator_proof=_proof(("network", "credential_material_access", "mcp_remote_tool", "live_transport")),
        opt_in_ref="live-opt-in://wave101/mcp",
        requested_transport_mode="live",
    )


def _different_provider_adapter_plan():
    return LiveProviderAdapterRuntime().plan(
        release=_provider_release(),
        provider_envelope=_provider_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave101-different-provider-adapter",
    )
