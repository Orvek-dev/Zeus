from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_mcp_owned_client_transport_runtime import (
    LiveMcpOwnedClientReceipt,
    LiveMcpOwnedClientRequest,
    LiveMcpOwnedClientTransportRuntime,
)
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave112_remote_executor_preflight import _mcp_handoff
from tests.test_wave115_mcp_external_transport import _mcp_policy, _mcp_preflight, _mcp_request


class _FakeMcpClient:
    def __init__(self, receipt: LiveMcpOwnedClientReceipt) -> None:
        self.receipt = receipt
        self.requests: list[LiveMcpOwnedClientRequest] = []

    def invoke(self, request: LiveMcpOwnedClientRequest) -> LiveMcpOwnedClientReceipt:
        self.requests.append(request)
        return self.receipt


def test_mcp_owned_client_executes_with_audit_redaction_and_teardown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    client = _FakeMcpClient(_receipt())

    result = LiveMcpOwnedClientTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        handoff=_mcp_handoff(),
        mcp_envelope=_mcp_request(),
        client=client,
        execution_ref="mcp-owned-client://wave119/github",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="mcp",
        execution=result,
        audit_ref="live-audit://wave119/mcp-owned-client",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_receipt().response_payload,
        response_ref="live-response://wave119/mcp-owned-client",
    )
    teardown = LiveTransportTeardownRuntime().record(
        home=tmp_path,
        adapter_kind="mcp",
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        execution=result,
        audit=audit,
        teardown_ref=_mcp_policy().teardown_ref or "",
    )

    assert result.decision == "executed"
    assert result.mcp_owned_client is True
    assert result.request_constructed is True
    assert result.header_value_ref_bound is True
    assert result.tool_invoked is True
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert client.requests[0].header_value_ref.startswith("secret-proof://")
    assert "mcp-" + "material-value" not in json.dumps(client.requests[0].to_payload())
    assert audit.decision == "audit_ready"
    assert redaction.decision == "redacted"
    assert teardown.decision == "teardown_recorded"


def test_mcp_owned_client_blocks_handoff_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    handoff = _mcp_handoff().model_copy(update={"policy_id": "wrong-policy"})

    result = LiveMcpOwnedClientTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        handoff=handoff,
        mcp_envelope=_mcp_request(),
        client=_FakeMcpClient(_receipt()),
        execution_ref="mcp-owned-client://wave119/mismatch",
    )

    assert result.decision == "blocked"
    assert "mcp_handoff_policy_mismatch" in result.blocked_reasons
    assert result.tool_invoked is False
    assert result.network_opened is False


def test_mcp_owned_client_blocks_server_or_resource_startup(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    receipt = _receipt().model_copy(update={"server_started": True, "resources_enabled": True})

    result = LiveMcpOwnedClientTransportRuntime().execute(
        policy=_mcp_policy(),
        preflight=_mcp_preflight(),
        handoff=_mcp_handoff(),
        mcp_envelope=_mcp_request(),
        client=_FakeMcpClient(receipt),
        execution_ref="mcp-owned-client://wave119/client-block",
    )

    assert result.decision == "blocked"
    assert "mcp_owned_client_server_started" in result.blocked_reasons
    assert "mcp_owned_client_resources_or_prompts_enabled" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_mcp_owned_client(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    policy = _mcp_policy()
    preflight = _mcp_preflight()
    handoff = _mcp_handoff()
    envelope = _mcp_request()
    receipt = _receipt()

    completed = CliRunner().invoke(
        app,
        [
            "live-mcp-owned-client-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--handoff-json",
            handoff.model_dump_json(),
            "--mcp-envelope-json",
            envelope.model_dump_json(),
            "--client-receipt-json",
            receipt.model_dump_json(),
            "--execution-ref",
            "mcp-owned-client://wave119/github",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_mcp_owned_client_transport(
        policy.to_payload(),
        preflight.to_payload(),
        handoff.to_payload(),
        envelope.to_payload(),
        receipt.model_dump(mode="json"),
        execution_ref="mcp-owned-client://wave119/github-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["mcp_owned_client"] is True
    assert payload["request_constructed"] is True
    assert payload["tool_invoked"] is True
    assert payload["server_started"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _receipt() -> LiveMcpOwnedClientReceipt:
    return LiveMcpOwnedClientReceipt(
        status_code=200,
        latency_ms=58,
        response_payload={"result": {"repositories": ["Orvek-dev/Zeus"]}, "debug": "token=ghp_" + "wave119"},
        network_opened=True,
        non_loopback_network_opened=True,
        server_started=False,
        resources_enabled=False,
        prompts_enabled=False,
        cleanup_receipt="mcp-owned-client-closed",
    )
