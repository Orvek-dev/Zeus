from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_production_claim_runtime import LiveProductionClaimRuntime
from zeus_agent.live_provider_direct_adapter_runtime import (
    LiveProviderDirectAdapterReceipt,
    LiveProviderDirectAdapterRequest,
    LiveProviderDirectAdapterRuntime,
)
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave107_provider_http_transport import _secret_material as _provider_secret_material
from tests.test_wave111_remote_credential_handoff import _provider_policy
from tests.test_wave112_remote_executor_preflight import _provider_handoff
from tests.test_wave113_provider_external_transport import _provider_request
from tests.test_wave121_live_production_claim import _production_approval


class _FakeProviderDirectClient:
    def __init__(self, receipt: LiveProviderDirectAdapterReceipt) -> None:
        self.receipt = receipt
        self.requests: list[LiveProviderDirectAdapterRequest] = []

    def send(self, request: LiveProviderDirectAdapterRequest) -> LiveProviderDirectAdapterReceipt:
        self.requests.append(request)
        return self.receipt


def test_provider_direct_adapter_executes_only_after_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    client = _FakeProviderDirectClient(_receipt())
    context = _provider_context(tmp_path)

    result = LiveProviderDirectAdapterRuntime().execute(
        claim=context["claim"],
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        provider_envelope=_provider_request(),
        client=client,
        execution_ref="provider-direct://wave122/provider",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=result,
        audit_ref="live-audit://wave122/provider-direct",
    )
    teardown = LiveTransportTeardownRuntime().record(
        home=tmp_path,
        adapter_kind="provider",
        policy=context["policy"],
        preflight=context["preflight"],
        execution=result,
        audit=audit,
        teardown_ref=context["policy"].teardown_ref or "",
    )

    assert result.decision == "executed"
    assert result.provider_direct_adapter is True
    assert result.production_claim_bound is True
    assert result.credential_injection_bound is True
    assert result.request_constructed is True
    assert result.provider_invoked is True
    assert result.non_loopback_network_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert client.requests[0].production_claim_id == context["claim"].claim_id
    assert client.requests[0].header_value_ref == context["injection"].header_value_ref
    assert "provider-" + "material-value" not in json.dumps(client.requests[0].to_payload())
    assert audit.decision == "audit_ready"
    assert teardown.decision == "teardown_recorded"


def test_provider_direct_adapter_blocks_without_claim(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderDirectAdapterRuntime().execute(
        claim=None,
        policy=_provider_policy(),
        preflight=None,
        handoff=_provider_handoff(),
        credential_injection=None,
        provider_envelope=_provider_request(),
        client=_FakeProviderDirectClient(_receipt()),
        execution_ref="provider-direct://wave122/no-claim",
    )

    assert result.decision == "blocked"
    assert "production_claim_required" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False


def test_provider_direct_adapter_audit_requires_claim_binding(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    context = _provider_context(tmp_path)
    result = LiveProviderDirectAdapterRuntime().execute(
        claim=context["claim"],
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        provider_envelope=_provider_request(),
        client=_FakeProviderDirectClient(_receipt()),
        execution_ref="provider-direct://wave122/no-claim-bound",
    ).model_copy(update={"production_claim_bound": False})

    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=result,
        audit_ref="live-audit://wave122/no-claim-bound",
    )

    assert audit.decision == "blocked"
    assert "provider_production_claim_not_bound" in audit.blocked_reasons


def test_provider_direct_adapter_blocks_wrong_claim_adapter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    claim = _mcp_claim(tmp_path)
    context = _provider_context(tmp_path)

    result = LiveProviderDirectAdapterRuntime().execute(
        claim=claim,
        policy=context["policy"],
        preflight=context["preflight"],
        handoff=context["handoff"],
        credential_injection=context["injection"],
        provider_envelope=_provider_request(),
        client=_FakeProviderDirectClient(_receipt()),
        execution_ref="provider-direct://wave122/wrong-claim",
    )

    assert result.decision == "blocked"
    assert "provider_production_claim_mismatch" in result.blocked_reasons
    assert result.network_opened is False


def test_cli_and_python_library_provider_direct_adapter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    context = _provider_context(tmp_path)
    claim = context["claim"]
    policy = context["policy"]
    preflight = context["preflight"]
    handoff = context["handoff"]
    injection = context["injection"]
    envelope = _provider_request()
    receipt = _receipt()

    completed = CliRunner().invoke(
        app,
        [
            "live-provider-direct-adapter",
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
            "--provider-envelope-json",
            envelope.model_dump_json(),
            "--client-receipt-json",
            receipt.model_dump_json(),
            "--execution-ref",
            "provider-direct://wave122/provider",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_provider_direct_adapter(
        claim.to_payload(),
        policy.to_payload(),
        preflight.to_payload(),
        handoff.to_payload(),
        injection.to_payload(),
        envelope.to_payload(),
        receipt.model_dump(mode="json"),
        execution_ref="provider-direct://wave122/provider-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["provider_direct_adapter"] is True
    assert payload["production_claim_bound"] is True
    assert payload["credential_injection_bound"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _provider_context(tmp_path: Path):
    claim = _provider_claim(tmp_path)
    policy = _provider_policy()
    handoff = _provider_handoff()
    preflight = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="provider",
        executor_ref="remote-executor://wave122/provider",
        idempotency_key="wave122-provider-direct",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )
    injection = LiveCredentialInjectionRuntime().prepare(
        adapter_kind="provider",
        claim=claim,
        policy=policy,
        preflight=preflight,
        handoff=handoff,
        secret_material=_provider_secret_material("api.openai.local"),
        injection_ref="credential-injection://wave122/provider",
    )
    return {"claim": claim, "policy": policy, "preflight": preflight, "handoff": handoff, "injection": injection}


def _provider_claim(tmp_path: Path):
    approval = _production_approval(tmp_path, "provider")
    return LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave122/provider",
    )


def _mcp_claim(tmp_path: Path):
    approval = _production_approval(tmp_path, "mcp")
    return LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave122/mcp",
    )


def _receipt() -> LiveProviderDirectAdapterReceipt:
    return LiveProviderDirectAdapterReceipt(
        status_code=200,
        latency_ms=44,
        response_payload={"answer": "direct provider response", "debug": "token=sk-" + "wave122"},
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="provider-direct-client-closed",
    )
