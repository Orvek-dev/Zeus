from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from tests.test_wave97_provider_adapter_plan import _provider_envelope, _release as _provider_release
from tests.test_wave98_gateway_adapter_plan import _gateway_envelope, _gateway_release
from tests.test_wave99_mcp_adapter_plan import _mcp_envelope, _mcp_release


def test_transport_opt_in_blocks_without_operator_proof(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveTransportOptInRuntime().record(
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(),
        operator_proof=None,
        opt_in_ref="live-opt-in://wave100/provider",
        requested_transport_mode="live",
    )

    assert result.decision == "blocked"
    assert "operator_proof_required" in result.blocked_reasons
    assert result.live_transport_opted_in is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_transport_opt_in_accepts_adapter_plans_for_all_surfaces(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    provider = LiveTransportOptInRuntime().record(
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(),
        operator_proof=_proof(("network", "credential_material_access", "external_provider_inference", "live_transport")),
        opt_in_ref="live-opt-in://wave100/provider",
        requested_transport_mode="live",
    )
    gateway = LiveTransportOptInRuntime().record(
        adapter_kind="gateway",
        adapter_plan=_gateway_adapter_plan(),
        operator_proof=_proof(("network", "credential_material_access", "external_delivery", "live_transport")),
        opt_in_ref="live-opt-in://wave100/gateway",
        requested_transport_mode="live",
    )
    mcp = LiveTransportOptInRuntime().record(
        adapter_kind="mcp",
        adapter_plan=_mcp_adapter_plan(),
        operator_proof=_proof(("network", "credential_material_access", "mcp_remote_tool", "live_transport")),
        opt_in_ref="live-opt-in://wave100/mcp",
        requested_transport_mode="live",
    )

    for result in (provider, gateway, mcp):
        assert result.decision == "opt_in_ready"
        assert result.live_transport_opted_in is True
        assert result.operator_proof_bound is True
        assert result.adapter_plan_bound is True
        assert result.live_transport_enabled is False
        assert result.network_opened is False
        assert result.credential_material_accessed is False
        assert result.live_production_claimed is False


def test_transport_opt_in_blocks_missing_risk_acknowledgement(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveTransportOptInRuntime().record(
        adapter_kind="provider",
        adapter_plan=_provider_adapter_plan(),
        operator_proof=_proof(("network", "credential_material_access")),
        opt_in_ref="live-opt-in://wave100/provider",
        requested_transport_mode="live",
    )

    assert result.decision == "blocked"
    assert "required_risk_not_acknowledged" in result.blocked_reasons
    assert result.live_transport_opted_in is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_transport_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    adapter_plan = _provider_adapter_plan()
    proof = _proof(("network", "credential_material_access", "external_provider_inference", "live_transport"))
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-transport-opt-in",
            "--adapter-kind",
            "provider",
            "--adapter-plan-json",
            adapter_plan.model_dump_json(),
            "--operator-proof-json",
            proof.model_dump_json(),
            "--opt-in-ref",
            "live-opt-in://wave100/provider",
            "--requested-transport-mode",
            "live",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "opt_in_ready"
    assert payload["live_transport_enabled"] is False

    library_payload = ZeusAgent().live_transport_opt_in(
        adapter_kind="provider",
        adapter_plan=adapter_plan.to_payload(),
        operator_proof=proof.to_payload(),
        opt_in_ref="live-opt-in://wave100/provider",
        requested_transport_mode="live",
    )
    assert library_payload["decision"] == "opt_in_ready"
    assert library_payload["network_opened"] is False


def _provider_adapter_plan():
    from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterRuntime

    return LiveProviderAdapterRuntime().plan(
        release=_provider_release(),
        provider_envelope=_provider_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave100-provider-adapter-1",
    )


def _gateway_adapter_plan():
    from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterRuntime

    return LiveGatewayAdapterRuntime().plan(
        release=_gateway_release(),
        gateway_envelope=_gateway_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave100-gateway-adapter-1",
    )


def _mcp_adapter_plan():
    from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterRuntime

    return LiveMcpAdapterRuntime().plan(
        release=_mcp_release(),
        mcp_envelope=_mcp_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave100-mcp-adapter-1",
    )


def _proof(reviewed_risks: tuple[str, ...]):
    return LiveOperatorProofRuntime().record(
        proof_id="wave100.proof.operator",
        operator_id="wave100.operator",
        execution_plan_id="live-execute-plan-wave100",
        proof_ref="operator-proof://wave100/live-transport",
        reviewed_risks=reviewed_risks,
    )
