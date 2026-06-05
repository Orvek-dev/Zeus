from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_owned_client_transport_runtime import (
    LiveProviderOwnedClientReceipt,
    LiveProviderOwnedClientRequest,
    LiveProviderOwnedClientTransportRuntime,
)
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from tests.test_wave111_remote_credential_handoff import _provider_policy
from tests.test_wave112_remote_executor_preflight import _provider_handoff
from tests.test_wave113_provider_external_transport import _provider_preflight, _provider_request


class _FakeProviderClient:
    def __init__(self, receipt: LiveProviderOwnedClientReceipt) -> None:
        self.receipt = receipt
        self.requests: list[LiveProviderOwnedClientRequest] = []

    def send(self, request: LiveProviderOwnedClientRequest) -> LiveProviderOwnedClientReceipt:
        self.requests.append(request)
        return self.receipt


def test_provider_owned_client_executes_with_audit_redaction_and_teardown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    client = _FakeProviderClient(_receipt())

    result = LiveProviderOwnedClientTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        handoff=_provider_handoff(),
        provider_envelope=_provider_request(),
        client=client,
        execution_ref="provider-owned-client://wave117/provider",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=result,
        audit_ref="live-audit://wave117/provider-owned-client",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_receipt().response_payload,
        response_ref="live-response://wave117/provider-owned-client",
    )
    teardown = LiveTransportTeardownRuntime().record(
        home=tmp_path,
        adapter_kind="provider",
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        execution=result,
        audit=audit,
        teardown_ref=_provider_policy().teardown_ref or "",
    )

    assert result.decision == "executed"
    assert result.provider_owned_client is True
    assert result.request_constructed is True
    assert result.header_value_ref_bound is True
    assert result.credential_handoff_bound is True
    assert result.provider_invoked is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert client.requests[0].header_value_ref.startswith("secret-proof://")
    assert "provider-" + "material-value" not in json.dumps(client.requests[0].to_payload())
    assert audit.decision == "audit_ready"
    assert redaction.decision == "redacted"
    assert teardown.decision == "teardown_recorded"


def test_provider_owned_client_blocks_handoff_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    handoff = _provider_handoff().model_copy(update={"policy_id": "wrong-policy"})

    result = LiveProviderOwnedClientTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        handoff=handoff,
        provider_envelope=_provider_request(),
        client=_FakeProviderClient(_receipt()),
        execution_ref="provider-owned-client://wave117/mismatch",
    )

    assert result.decision == "blocked"
    assert "provider_handoff_policy_mismatch" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False


def test_provider_owned_client_blocks_secret_echo(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    receipt = _receipt().model_copy(update={"response_payload": {"debug": "token=sk-" + "wave117"}})

    result = LiveProviderOwnedClientTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        handoff=_provider_handoff(),
        provider_envelope=_provider_request(),
        client=_FakeProviderClient(receipt),
        execution_ref="provider-owned-client://wave117/secret-echo",
    )

    assert result.decision == "executed"
    assert "sk-" + "wave117" not in json.dumps(result.to_payload())
    assert result.no_secret_echo is True


def test_cli_and_python_library_provider_owned_client(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    policy = _provider_policy()
    preflight = _provider_preflight()
    handoff = _provider_handoff()
    envelope = _provider_request()
    receipt = _receipt()

    completed = CliRunner().invoke(
        app,
        [
            "live-provider-owned-client-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--handoff-json",
            handoff.model_dump_json(),
            "--provider-envelope-json",
            envelope.model_dump_json(),
            "--client-receipt-json",
            receipt.model_dump_json(),
            "--execution-ref",
            "provider-owned-client://wave117/provider",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_provider_owned_client_transport(
        policy.to_payload(),
        preflight.to_payload(),
        handoff.to_payload(),
        envelope.to_payload(),
        receipt.model_dump(mode="json"),
        execution_ref="provider-owned-client://wave117/provider-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["provider_owned_client"] is True
    assert payload["request_constructed"] is True
    assert payload["header_value_ref_bound"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _receipt() -> LiveProviderOwnedClientReceipt:
    return LiveProviderOwnedClientReceipt(
        status_code=200,
        latency_ms=47,
        response_payload={"answer": "owned provider client response"},
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="provider-owned-client-closed",
    )
