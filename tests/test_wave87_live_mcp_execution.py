from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_mcp_execution_runtime import LiveMcpExecutionRuntime


def test_live_mcp_execution_blocks_without_ready_envelope() -> None:
    result = LiveMcpExecutionRuntime().invoke(
        readiness=None,
        tool_name="mcp.echo",
        arguments={"text": "hello"},
    )

    assert result.decision == "blocked"
    assert "execution_readiness_required" in result.blocked_reasons
    assert result.tool_invoked is False
    assert result.server_started is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_mcp_execution_invokes_local_echo_without_starting_server() -> None:
    result = LiveMcpExecutionRuntime().invoke(
        readiness=_mcp_readiness(),
        tool_name="mcp.echo",
        arguments={"text": "hello"},
    )

    assert result.decision == "selected"
    assert result.tool_invoked is True
    assert result.output == {"text": "hello"}
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.network_opened is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_mcp_execution_blocks_unknown_tool() -> None:
    result = LiveMcpExecutionRuntime().invoke(
        readiness=_mcp_readiness(),
        tool_name="mcp.admin",
        arguments={"text": "hello"},
    )

    assert result.decision == "blocked"
    assert "unsupported_mcp_tool" in result.blocked_reasons
    assert result.tool_invoked is False
    assert result.server_started is False


def test_cli_and_python_library_live_mcp_execution() -> None:
    readiness = _mcp_readiness()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-mcp-invoke",
            "--readiness-json",
            readiness.model_dump_json(),
            "--tool-name",
            "mcp.echo",
            "--arguments-json",
            json.dumps({"text": "hello"}),
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "selected"
    assert payload["server_started"] is False

    library_payload = ZeusAgent().live_mcp_invoke(
        readiness.to_payload(),
        tool_name="mcp.echo",
        arguments={"text": "hello"},
    )
    assert library_payload["decision"] == "selected"
    assert library_payload["tool_invoked"] is True


def _mcp_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="wave87.readiness.mcp",
        execution_plan_id="live-execute-plan-wave87",
        handoff_manifest_id="live-handoff-wave87",
        surface_kind="mcp",
        surface_id="mcp.catalog",
        capability_id="mcp.echo",
        credential_bindings_ready=True,
        gateway_pairing_ready=True,
        secret_resolver_ready=True,
        operator_proof_bound=True,
        blocked_reasons=(),
        gate_summary={
            "credential_bindings_ready": True,
            "gateway_pairing_ready": True,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        operator_proof_summary={
            "proof_id": "wave87.proof.operator",
            "operator_reviewed": True,
            "execution_authorized": False,
        },
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
