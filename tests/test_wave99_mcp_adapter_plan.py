from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from tests.test_wave93_mcp_request_envelope import _mcp_transport_lease, _secret_material
from tests.test_wave94_execution_authorization import _operator_proof


def test_mcp_adapter_plan_blocks_without_release(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpAdapterRuntime().plan(
        release=None,
        mcp_envelope=_mcp_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave99-mcp-adapter-1",
    )

    assert result.decision == "blocked"
    assert "executor_release_required" in result.blocked_reasons
    assert result.adapter_plan_ready is False
    assert result.tool_invoked is False
    assert result.live_production_claimed is False


def test_mcp_adapter_plan_prepares_dry_run_without_invocation(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpAdapterRuntime().plan(
        release=_mcp_release(),
        mcp_envelope=_mcp_envelope(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave99-mcp-adapter-1",
    )

    assert result.decision == "planned"
    assert result.adapter_plan_ready is True
    assert result.release_bound is True
    assert result.mcp_envelope_bound is True
    assert result.live_transport_requested is False
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.tool_invoked is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_transport_enabled is False
    assert result.live_production_claimed is False


def test_mcp_adapter_plan_blocks_live_transport_until_executor_exists(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpAdapterRuntime().plan(
        release=_mcp_release(),
        mcp_envelope=_mcp_envelope(),
        transport_mode="live",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave99-mcp-adapter-1",
    )

    assert result.decision == "blocked"
    assert "mcp_live_transport_not_implemented" in result.blocked_reasons
    assert result.live_transport_requested is True
    assert result.tool_invoked is False
    assert result.network_opened is False


def test_cli_and_python_library_mcp_adapter_plan(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")
    release = _mcp_release()
    envelope = _mcp_envelope()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-mcp-adapter-plan",
            "--release-json",
            release.model_dump_json(),
            "--mcp-envelope-json",
            envelope.model_dump_json(),
            "--transport-mode",
            "dry_run",
            "--timeout-ms",
            "1500",
            "--retry-attempts",
            "1",
            "--idempotency-key",
            "wave99-mcp-adapter-1",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "planned"
    assert payload["tool_invoked"] is False

    library_payload = ZeusAgent().live_mcp_adapter_plan(
        release.to_payload(),
        mcp_envelope=envelope.to_payload(),
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=1,
        idempotency_key="wave99-mcp-adapter-1",
    )
    assert library_payload["decision"] == "planned"
    assert library_payload["server_started"] is False


def _mcp_envelope():
    return LiveMcpRequestRuntime().prepare(
        transport_lease=_mcp_transport_lease(),
        secret_material=_secret_material(),
        server_id="mcp.github",
        tool_name="repo.search",
        endpoint="https://mcp.github.local/rpc",
        arguments={"query": "Zeus"},
    )


def _mcp_release():
    risks = ("network", "credential_material_access", "mcp_remote_tool")
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="mcp",
        envelope=_mcp_envelope().to_payload(),
        operator_proof=_operator_proof(reviewed_risks=risks),
        required_risks=risks,
    )
    return LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="mcp",
        release_ref="executor-release://wave99/mcp",
        idempotency_key="wave99-mcp-release-1",
    )
