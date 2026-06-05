from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_mcp_remote_adapter_runtime import (
    LiveMcpRemoteAdapterReceipt,
    LiveMcpRemoteAdapterRequest,
    LiveMcpRemoteAdapterRuntime,
)
from zeus_agent.live_production_claim_runtime import LiveProductionClaimRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave109_mcp_http_transport import _secret_material as _mcp_secret_material
from tests.test_wave112_remote_executor_preflight import _mcp_handoff
from tests.test_wave115_mcp_external_transport import _mcp_policy, _mcp_preflight, _mcp_request
from tests.test_wave121_live_production_claim import _production_approval


class _FakeMcpRemoteClient:
    def __init__(self, receipt: LiveMcpRemoteAdapterReceipt) -> None:
        self.receipt = receipt
        self.requests: list[LiveMcpRemoteAdapterRequest] = []

    def invoke(self, request: LiveMcpRemoteAdapterRequest) -> LiveMcpRemoteAdapterReceipt:
        self.requests.append(request)
        return self.receipt


def test_mcp_remote_adapter_executes_only_after_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    client = _FakeMcpRemoteClient(_receipt())
    context = _mcp_context(tmp_path)

    result = LiveMcpRemoteAdapterRuntime().execute(
        claim=context["claim"],
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        mcp_envelope=_mcp_request(),
        client=client,
        execution_ref="mcp-remote://wave124/github",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="mcp",
        execution=result,
        audit_ref="live-audit://wave124/mcp-remote",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_receipt().response_payload,
        response_ref="live-response://wave124/mcp-remote",
    )
    teardown = LiveTransportTeardownRuntime().record(
        home=tmp_path,
        adapter_kind="mcp",
        policy=context["policy"],
        preflight=context["preflight"],
        execution=result,
        audit=audit,
        teardown_ref=context["policy"].teardown_ref or "",
    )

    assert result.decision == "executed"
    assert result.mcp_remote_adapter is True
    assert result.production_claim_bound is True
    assert result.credential_injection_bound is True
    assert result.tool_invoked is True
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.network_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert client.requests[0].production_claim_id == context["claim"].claim_id
    assert client.requests[0].header_value_ref == context["injection"].header_value_ref
    assert "mcp-" + "material-value" not in json.dumps(client.requests[0].to_payload())
    assert audit.decision == "audit_ready"
    assert redaction.decision == "redacted"
    assert teardown.decision == "teardown_recorded"


def test_mcp_remote_adapter_blocks_without_claim(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpRemoteAdapterRuntime().execute(
        claim=None,
        policy=_mcp_policy(),
        preflight=None,
        handoff=_mcp_handoff(),
        credential_injection=None,
        mcp_envelope=_mcp_request(),
        client=_FakeMcpRemoteClient(_receipt()),
        execution_ref="mcp-remote://wave124/no-claim",
    )

    assert result.decision == "blocked"
    assert "production_claim_required" in result.blocked_reasons
    assert result.tool_invoked is False
    assert result.network_opened is False


def test_mcp_remote_adapter_audit_requires_claim_binding(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    context = _mcp_context(tmp_path)
    result = LiveMcpRemoteAdapterRuntime().execute(
        claim=context["claim"],
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        mcp_envelope=_mcp_request(),
        client=_FakeMcpRemoteClient(_receipt()),
        execution_ref="mcp-remote://wave124/no-claim-bound",
    ).model_copy(update={"production_claim_bound": False})

    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="mcp",
        execution=result,
        audit_ref="live-audit://wave124/no-claim-bound",
    )

    assert audit.decision == "blocked"
    assert "mcp_production_claim_not_bound" in audit.blocked_reasons


def test_mcp_remote_adapter_blocks_wrong_claim_adapter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    claim = _provider_claim(tmp_path)
    context = _mcp_context(tmp_path)

    result = LiveMcpRemoteAdapterRuntime().execute(
        claim=claim,
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        mcp_envelope=_mcp_request(),
        client=_FakeMcpRemoteClient(_receipt()),
        execution_ref="mcp-remote://wave124/wrong-claim",
    )

    assert result.decision == "blocked"
    assert "mcp_production_claim_mismatch" in result.blocked_reasons
    assert result.network_opened is False


def test_mcp_remote_adapter_blocks_server_or_resource_startup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    receipt = _receipt().model_copy(update={"server_started": True, "resources_enabled": True})
    context = _mcp_context(tmp_path)

    result = LiveMcpRemoteAdapterRuntime().execute(
        claim=context["claim"],
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        mcp_envelope=_mcp_request(),
        client=_FakeMcpRemoteClient(receipt),
        execution_ref="mcp-remote://wave124/server-block",
    )

    assert result.decision == "blocked"
    assert "mcp_remote_adapter_server_started" in result.blocked_reasons
    assert "mcp_remote_adapter_resources_or_prompts_enabled" in result.blocked_reasons
    assert result.network_opened is False


def test_cli_and_python_library_mcp_remote_adapter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    context = _mcp_context(tmp_path)
    claim = context["claim"]
    policy = context["policy"]
    preflight = context["preflight"]
    handoff = context["handoff"]
    injection = context["injection"]
    envelope = _mcp_request()
    receipt = _receipt()

    completed = CliRunner().invoke(
        app,
        [
            "live-mcp-remote-adapter",
            "--claim-json",
            claim.model_dump_json(),
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--handoff-json",
            handoff.model_dump_json(),
            "--credential-injection-json",
            injection.model_dump_json(),
            "--mcp-envelope-json",
            envelope.model_dump_json(),
            "--client-receipt-json",
            receipt.model_dump_json(),
            "--execution-ref",
            "mcp-remote://wave124/github",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_mcp_remote_adapter(
        claim.to_payload(),
        policy.to_payload(),
        preflight.to_payload(),
        handoff.to_payload(),
        injection.to_payload(),
        envelope.to_payload(),
        receipt.model_dump(mode="json"),
        execution_ref="mcp-remote://wave124/github-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["mcp_remote_adapter"] is True
    assert payload["production_claim_bound"] is True
    assert payload["credential_injection_bound"] is True
    assert payload["server_started"] is False
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _mcp_context(tmp_path: Path):
    claim = _mcp_claim(tmp_path)
    policy = _mcp_policy()
    preflight = _mcp_preflight()
    handoff = _mcp_handoff()
    injection = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="mcp",
        claim=claim,
        policy=policy,
        preflight=preflight,
        handoff=handoff,
        secret_material=_mcp_secret_material("mcp.github.local"),
        injection_ref="credential-injection://wave124/mcp",
    )
    return {"claim": claim, "policy": policy, "preflight": preflight, "handoff": handoff, "injection": injection}


def _mcp_claim(tmp_path: Path):
    approval = _production_approval(tmp_path, "mcp")
    return LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave124/mcp",
    )


def _provider_claim(tmp_path: Path):
    approval = _production_approval(tmp_path, "provider")
    return LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave124/provider",
    )


def _receipt() -> LiveMcpRemoteAdapterReceipt:
    return LiveMcpRemoteAdapterReceipt(
        status_code=200,
        latency_ms=61,
        response_payload={"result": {"repositories": ["Orvek-dev/Zeus"]}, "debug": "token=ghp_" + "wave124"},
        network_opened=True,
        non_loopback_network_opened=True,
        server_started=False,
        resources_enabled=False,
        prompts_enabled=False,
        cleanup_receipt="mcp-remote-adapter-client-closed",
    )
