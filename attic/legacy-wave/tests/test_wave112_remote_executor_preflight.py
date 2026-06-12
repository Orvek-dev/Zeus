from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffRuntime
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from tests.test_wave107_provider_http_transport import _secret_material as _provider_secret_material
from tests.test_wave109_mcp_http_transport import _secret_material as _mcp_secret_material
from tests.test_wave111_remote_credential_handoff import _gateway_policy, _mcp_policy, _provider_policy
from tests.test_wave92_gateway_delivery_envelope import _secret_material as _gateway_secret_material


def test_remote_executor_preflight_ready_without_live_side_effects(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    policy = _provider_policy()

    result = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=_provider_handoff(),
        executor_kind="provider",
        executor_ref="remote-executor://wave112/provider",
        idempotency_key="wave112-provider-preflight-1",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )

    assert result.decision == "preflight_ready"
    assert result.remote_executor_preflight_ready is True
    assert result.policy_bound is True
    assert result.credential_handoff_bound is True
    assert result.idempotency_bound is True
    assert result.timeout_retry_bound is True
    assert result.teardown_bound is True
    assert result.execution_allowed is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False


def test_remote_executor_preflight_accepts_gateway_and_mcp(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    gateway_policy = _gateway_policy()
    mcp_policy = _mcp_policy()

    gateway = LiveRemoteExecutorPreflightRuntime().plan(
        policy=gateway_policy,
        handoff=_gateway_handoff(),
        executor_kind="gateway",
        executor_ref="remote-executor://wave112/gateway",
        idempotency_key="wave112-gateway-preflight-1",
        teardown_ref=gateway_policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=0,
    )
    mcp = LiveRemoteExecutorPreflightRuntime().plan(
        policy=mcp_policy,
        handoff=_mcp_handoff(),
        executor_kind="mcp",
        executor_ref="remote-executor://wave112/mcp",
        idempotency_key="wave112-mcp-preflight-1",
        teardown_ref=mcp_policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=0,
    )

    for result in (gateway, mcp):
        assert result.decision == "preflight_ready"
        assert result.remote_executor_preflight_ready is True
        assert result.network_opened is False
        assert result.external_delivery_opened is False
        assert result.live_production_claimed is False


def test_remote_executor_preflight_blocks_handoff_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    policy = _provider_policy()

    result = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=_mcp_handoff(),
        executor_kind="provider",
        executor_ref="remote-executor://wave112/provider",
        idempotency_key="wave112-provider-preflight-1",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=0,
    )

    assert result.decision == "blocked"
    assert "credential_handoff_policy_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.raw_secret_returned is False


def test_remote_executor_preflight_blocks_policy_bounds(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    policy = _provider_policy()

    result = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=_provider_handoff(),
        executor_kind="provider",
        executor_ref="",
        idempotency_key="",
        teardown_ref="teardown://wrong",
        timeout_ms=0,
        retry_attempts=4,
    )

    assert result.decision == "blocked"
    assert "executor_ref_required" in result.blocked_reasons
    assert "idempotency_key_required" in result.blocked_reasons
    assert "timeout_retry_out_of_bounds" in result.blocked_reasons
    assert "teardown_ref_policy_mismatch" in result.blocked_reasons


def test_cli_and_python_library_remote_executor_preflight(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    policy = _provider_policy()
    handoff = _provider_handoff()
    completed = CliRunner().invoke(
        app,
        [
            "live-remote-executor-preflight",
            "--policy-json",
            policy.model_dump_json(),
            "--handoff-json",
            handoff.model_dump_json(),
            "--executor-kind",
            "provider",
            "--executor-ref",
            "remote-executor://wave112/provider",
            "--idempotency-key",
            "wave112-provider-preflight-1",
            "--teardown-ref",
            policy.teardown_ref or "",
            "--timeout-ms",
            "1500",
            "--retry-attempts",
            "1",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_remote_executor_preflight(
        policy.to_payload(),
        handoff.to_payload(),
        executor_kind="provider",
        executor_ref="remote-executor://wave112/provider-library",
        idempotency_key="wave112-provider-preflight-library",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "preflight_ready"
    assert payload["network_opened"] is False
    assert payload["execution_allowed"] is False
    assert library_payload["decision"] == "preflight_ready"
    assert library_payload["live_production_claimed"] is False


def _provider_handoff():
    return LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_provider_policy(),
        secret_material=_provider_secret_material("api.openai.local"),
        handoff_ref="credential-handoff://wave112/provider",
        auth_scheme="bearer",
        header_name="Authorization",
    )


def _gateway_handoff():
    return LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_gateway_policy(),
        secret_material=_gateway_secret_material(),
        handoff_ref="credential-handoff://wave112/gateway",
        auth_scheme="bearer",
        header_name="Authorization",
    )


def _mcp_handoff():
    return LiveRemoteCredentialHandoffRuntime().prepare(
        policy=_mcp_policy(),
        secret_material=_mcp_secret_material("mcp.github.local"),
        handoff_ref="credential-handoff://wave112/mcp",
        auth_scheme="api_key",
        header_name="X-API-Key",
    )
