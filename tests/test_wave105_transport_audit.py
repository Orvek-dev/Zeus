from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from tests.test_wave102_provider_loopback_transport import (
    _provider_activation,
    _provider_adapter_plan,
    _provider_envelope,
)
from tests.test_wave103_gateway_loopback_transport import (
    _gateway_activation,
    _gateway_adapter_plan,
    _gateway_envelope,
)
from tests.test_wave104_mcp_loopback_transport import (
    _mcp_activation,
    _mcp_adapter_plan,
    _mcp_envelope,
)


def test_transport_audit_blocks_missing_execution() -> None:
    result = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=None,
        audit_ref="live-audit://wave105/missing",
    )

    assert result.decision == "blocked"
    assert "execution_result_required" in result.blocked_reasons
    assert result.post_execution_audit_ready is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_transport_audit_accepts_provider_loopback(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=_provider_execution(),
        audit_ref="live-audit://wave105/provider",
    )

    assert result.decision == "audit_ready"
    assert result.execution_result_bound is True
    assert result.cleanup_receipt_verified is True
    assert result.external_side_effects_absent is True
    assert result.execution_live_transport_seen is True
    assert result.post_execution_audit_ready is True
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_transport_audit_accepts_gateway_and_mcp_loopbacks(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")
    runtime = LiveTransportAuditRuntime()

    gateway_result = runtime.audit(
        adapter_kind="gateway",
        execution=_gateway_execution(),
        audit_ref="live-audit://wave105/gateway",
    )
    mcp_result = runtime.audit(
        adapter_kind="mcp",
        execution=_mcp_execution(),
        audit_ref="live-audit://wave105/mcp",
    )

    assert gateway_result.decision == "audit_ready"
    assert gateway_result.cleanup_receipt == "gateway-loopback-no-delivery"
    assert gateway_result.external_side_effects_absent is True
    assert mcp_result.decision == "audit_ready"
    assert mcp_result.cleanup_receipt == "mcp-loopback-no-remote-server"
    assert mcp_result.external_side_effects_absent is True


def test_transport_audit_blocks_missing_cleanup_and_side_effects(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    execution = _provider_execution().model_copy(
        update={"cleanup_receipt": None, "network_opened": True}
    )

    result = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=execution,
        audit_ref="live-audit://wave105/provider",
    )

    assert result.decision == "blocked"
    assert "cleanup_receipt_invalid" in result.blocked_reasons
    assert "provider_network_opened" in result.blocked_reasons
    assert result.post_execution_audit_ready is False
    assert result.external_side_effects_absent is False


def test_cli_and_python_library_transport_audit(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    execution = _provider_execution()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-transport-audit",
            "--adapter-kind",
            "provider",
            "--execution-json",
            execution.model_dump_json(),
            "--audit-ref",
            "live-audit://wave105/provider",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "audit_ready"
    assert payload["live_transport_enabled"] is False

    library_payload = ZeusAgent().live_transport_audit(
        adapter_kind="provider",
        execution=execution.to_payload(),
        audit_ref="live-audit://wave105/provider",
    )
    assert library_payload["decision"] == "audit_ready"
    assert library_payload["cleanup_receipt_verified"] is True


def _provider_execution():
    from zeus_agent.live_provider_loopback_transport_runtime import (
        LiveProviderLoopbackTransportRuntime,
    )

    return LiveProviderLoopbackTransportRuntime().execute(
        activation=_provider_activation(),
        adapter_plan=_provider_adapter_plan(),
        provider_envelope=_provider_envelope(),
        transport_kind="loopback_http",
        execution_ref="provider-loopback://wave105/provider",
    )


def _gateway_execution():
    from zeus_agent.live_gateway_loopback_transport_runtime import (
        LiveGatewayLoopbackTransportRuntime,
    )

    return LiveGatewayLoopbackTransportRuntime().execute(
        activation=_gateway_activation(),
        adapter_plan=_gateway_adapter_plan(),
        gateway_envelope=_gateway_envelope(),
        transport_kind="loopback_delivery",
        execution_ref="gateway-loopback://wave105/gateway",
    )


def _mcp_execution():
    from zeus_agent.live_mcp_loopback_transport_runtime import LiveMcpLoopbackTransportRuntime

    return LiveMcpLoopbackTransportRuntime().execute(
        activation=_mcp_activation(),
        adapter_plan=_mcp_adapter_plan(),
        mcp_envelope=_mcp_envelope(),
        transport_kind="loopback_tool",
        execution_ref="mcp-loopback://wave105/mcp",
    )
