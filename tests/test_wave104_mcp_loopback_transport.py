from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_mcp_loopback_transport_runtime import LiveMcpLoopbackTransportRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from tests.test_wave100_live_transport_opt_in import _mcp_adapter_plan
from tests.test_wave101_transport_activation_plan import _mcp_opt_in
from tests.test_wave93_mcp_request_envelope import _mcp_transport_lease, _secret_material
from tests.test_wave99_mcp_adapter_plan import _mcp_envelope


def test_mcp_loopback_transport_blocks_without_activation(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpLoopbackTransportRuntime().execute(
        activation=None,
        adapter_plan=_mcp_adapter_plan(),
        mcp_envelope=_mcp_envelope(),
        transport_kind="loopback_tool",
        execution_ref="mcp-loopback://wave104/mcp",
    )

    assert result.decision == "blocked"
    assert "transport_activation_required" in result.blocked_reasons
    assert result.tool_invoked is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_mcp_loopback_transport_executes_without_remote_server(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpLoopbackTransportRuntime().execute(
        activation=_mcp_activation(),
        adapter_plan=_mcp_adapter_plan(),
        mcp_envelope=_mcp_envelope(),
        transport_kind="loopback_tool",
        execution_ref="mcp-loopback://wave104/mcp",
    )

    assert result.decision == "executed"
    assert result.transport_activation_bound is True
    assert result.adapter_plan_bound is True
    assert result.mcp_envelope_bound is True
    assert result.loopback_transport is True
    assert result.tool_invoked is True
    assert result.handler_executed is True
    assert result.live_transport_enabled is True
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert result.cleanup_receipt == "mcp-loopback-no-remote-server"


def test_mcp_loopback_transport_blocks_remote_server(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpLoopbackTransportRuntime().execute(
        activation=_mcp_activation(),
        adapter_plan=_mcp_adapter_plan(),
        mcp_envelope=_mcp_envelope(),
        transport_kind="remote_server",
        execution_ref="mcp-loopback://wave104/mcp",
    )

    assert result.decision == "blocked"
    assert "mcp_remote_server_not_implemented" in result.blocked_reasons
    assert result.server_started is False
    assert result.tool_invoked is False
    assert result.network_opened is False


def test_mcp_loopback_transport_blocks_envelope_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpLoopbackTransportRuntime().execute(
        activation=_mcp_activation(),
        adapter_plan=_mcp_adapter_plan(),
        mcp_envelope=_different_mcp_envelope(),
        transport_kind="loopback_tool",
        execution_ref="mcp-loopback://wave104/mcp",
    )

    assert result.decision == "blocked"
    assert "adapter_mcp_envelope_mismatch" in result.blocked_reasons
    assert result.tool_invoked is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_mcp_loopback_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")
    activation = _mcp_activation()
    adapter_plan = _mcp_adapter_plan()
    envelope = _mcp_envelope()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-mcp-loopback-transport",
            "--activation-json",
            activation.model_dump_json(),
            "--adapter-plan-json",
            adapter_plan.model_dump_json(),
            "--mcp-envelope-json",
            envelope.model_dump_json(),
            "--transport-kind",
            "loopback_tool",
            "--execution-ref",
            "mcp-loopback://wave104/mcp",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["server_started"] is False

    library_payload = ZeusAgent().live_mcp_loopback_transport(
        activation.to_payload(),
        adapter_plan=adapter_plan.to_payload(),
        mcp_envelope=envelope.to_payload(),
        transport_kind="loopback_tool",
        execution_ref="mcp-loopback://wave104/mcp",
    )
    assert library_payload["decision"] == "executed"
    assert library_payload["network_opened"] is False


def _mcp_activation():
    return LiveTransportActivationRuntime().plan(
        opt_in=_mcp_opt_in(),
        adapter_kind="mcp",
        adapter_plan=_mcp_adapter_plan(),
        activation_ref="live-activation://wave104/mcp",
    )


def _different_mcp_envelope():
    return LiveMcpRequestRuntime().prepare(
        transport_lease=_mcp_transport_lease(),
        secret_material=_secret_material(),
        server_id="mcp.github",
        tool_name="repo.search",
        endpoint="https://mcp.github.local/rpc",
        arguments={"query": "Different Zeus"},
    )
