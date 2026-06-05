from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_mcp_external_transport_runtime import (
    LiveMcpExternalClientResult,
    LiveMcpExternalTransportRuntime,
)
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from tests.test_wave109_mcp_http_transport import _mcp_envelope
from tests.test_wave111_remote_credential_handoff import _mcp_policy
from tests.test_wave112_remote_executor_preflight import _mcp_handoff


def test_mcp_external_transport_executes_with_controlled_audit_and_redaction(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpExternalTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        mcp_envelope=_mcp_request(),
        client_result=_client_result(),
        execution_ref="mcp-external://wave115/github",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="mcp",
        execution=result,
        audit_ref="live-audit://wave115/mcp-external",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_client_result().response_payload,
        response_ref="live-response://wave115/mcp-external",
    )

    assert result.decision == "executed"
    assert result.policy_bound is True
    assert result.remote_executor_preflight_bound is True
    assert result.mcp_envelope_bound is True
    assert result.tool_invoked is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.cleanup_receipt == "mcp-remote-server-client-closed"
    assert "ghp_" + "wave115" not in json.dumps(result.to_payload())
    assert audit.decision == "audit_ready"
    assert audit.controlled_external_side_effects is True
    assert audit.external_side_effects_absent is False
    assert redaction.decision == "redacted"
    assert redaction.no_secret_echo is True
    assert result.live_production_claimed is False


def test_mcp_external_transport_blocks_endpoint_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpExternalTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        mcp_envelope=_mcp_envelope("https://evil.local/rpc", "evil.local"),
        client_result=_client_result(),
        execution_ref="mcp-external://wave115/mismatch",
    )

    assert result.decision == "blocked"
    assert "mcp_remote_target_mismatch" in result.blocked_reasons
    assert "mcp_preflight_endpoint_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.tool_invoked is False


def test_mcp_external_transport_blocks_server_or_resource_startup(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    client_result = _client_result().model_copy(update={"server_started": True, "resources_enabled": True})

    result = LiveMcpExternalTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        mcp_envelope=_mcp_request(),
        client_result=client_result,
        execution_ref="mcp-external://wave115/client-block",
    )

    assert result.decision == "blocked"
    assert "mcp_external_server_started" in result.blocked_reasons
    assert "mcp_external_resources_or_prompts_enabled" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_mcp_external_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    policy = _mcp_policy()
    preflight = _mcp_preflight()
    envelope = _mcp_request()
    client_result = _client_result()

    completed = CliRunner().invoke(
        app,
        [
            "live-mcp-external-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--mcp-envelope-json",
            envelope.model_dump_json(),
            "--client-result-json",
            client_result.model_dump_json(),
            "--execution-ref",
            "mcp-external://wave115/github",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_mcp_external_transport(
        policy.to_payload(),
        preflight.to_payload(),
        envelope.to_payload(),
        client_result.model_dump(mode="json"),
        execution_ref="mcp-external://wave115/github-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is True
    assert payload["server_started"] is False
    assert payload["resources_enabled"] is False
    assert payload["prompts_enabled"] is False
    assert payload["controlled_external_side_effects"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _mcp_request():
    return _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")


def _mcp_preflight():
    policy = _mcp_policy()
    return LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=_mcp_handoff(),
        executor_kind="mcp",
        executor_ref="remote-executor://wave115/mcp",
        idempotency_key="wave115-mcp-external",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )


def _client_result() -> LiveMcpExternalClientResult:
    return LiveMcpExternalClientResult(
        status_code=200,
        latency_ms=61,
        response_payload={
            "result": {"repositories": ["Orvek-dev/Zeus"]},
            "debug": "token=ghp_" + "wave115",
        },
        network_opened=True,
        non_loopback_network_opened=True,
        server_started=False,
        resources_enabled=False,
        prompts_enabled=False,
        cleanup_receipt="mcp-remote-server-client-closed",
    )
