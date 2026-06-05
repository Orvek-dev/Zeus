from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_external_transport_runtime import (
    LiveProviderExternalClientResult,
    LiveProviderExternalTransportRuntime,
)
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffRuntime
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from tests.test_wave107_provider_http_transport import _provider_envelope, _secret_material
from tests.test_wave111_remote_credential_handoff import _provider_policy


def test_provider_external_transport_executes_with_controlled_audit_and_redaction(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderExternalTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        provider_envelope=_provider_request(),
        client_result=_client_result(),
        execution_ref="provider-external://wave113/provider",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=result,
        audit_ref="live-audit://wave113/provider-external",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=_client_result().response_payload,
        response_ref="live-response://wave113/provider-external",
    )

    assert result.decision == "executed"
    assert result.policy_bound is True
    assert result.remote_executor_preflight_bound is True
    assert result.provider_envelope_bound is True
    assert result.provider_invoked is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.cleanup_receipt == "provider-external-http-client-closed"
    assert "sk-" + "wave113" not in json.dumps(result.to_payload())
    assert audit.decision == "audit_ready"
    assert audit.controlled_external_side_effects is True
    assert audit.external_side_effects_absent is False
    assert redaction.decision == "redacted"
    assert redaction.no_secret_echo is True
    assert result.live_production_claimed is False


def test_provider_external_transport_blocks_endpoint_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")

    result = LiveProviderExternalTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        provider_envelope=_provider_envelope("https://evil.openai.local/v1/chat/completions", "evil.openai.local"),
        client_result=_client_result(),
        execution_ref="provider-external://wave113/mismatch",
    )

    assert result.decision == "blocked"
    assert "provider_remote_target_mismatch" in result.blocked_reasons
    assert "provider_preflight_endpoint_mismatch" in result.blocked_reasons
    assert result.network_opened is False
    assert result.provider_invoked is False


def test_provider_external_transport_blocks_unconfirmed_client_network(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    client_result = _client_result().model_copy(update={"non_loopback_network_opened": False})

    result = LiveProviderExternalTransportRuntime().execute(
        policy=_provider_policy(),
        preflight=_provider_preflight(),
        provider_envelope=_provider_request(),
        client_result=client_result,
        execution_ref="provider-external://wave113/client-block",
    )

    assert result.decision == "blocked"
    assert "provider_external_network_not_confirmed" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_transport_enabled is False


def test_cli_and_python_library_provider_external_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    policy = _provider_policy()
    preflight = _provider_preflight()
    envelope = _provider_request()
    client_result = _client_result()

    completed = CliRunner().invoke(
        app,
        [
            "live-provider-external-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--preflight-json",
            preflight.model_dump_json(),
            "--provider-envelope-json",
            envelope.model_dump_json(),
            "--client-result-json",
            client_result.model_dump_json(),
            "--execution-ref",
            "provider-external://wave113/provider",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_provider_external_transport(
        policy.to_payload(),
        preflight.to_payload(),
        envelope.to_payload(),
        client_result.model_dump(mode="json"),
        execution_ref="provider-external://wave113/provider-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is True
    assert payload["controlled_external_side_effects"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _provider_request():
    return _provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")


def _provider_preflight():
    policy = _provider_policy()
    handoff = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=policy,
        secret_material=_secret_material("api.openai.local"),
        handoff_ref="credential-handoff://wave113/provider",
        auth_scheme="bearer",
        header_name="Authorization",
    )
    return LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="provider",
        executor_ref="remote-executor://wave113/provider",
        idempotency_key="wave113-provider-external",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )


def _client_result() -> LiveProviderExternalClientResult:
    return LiveProviderExternalClientResult(
        status_code=200,
        latency_ms=44,
        response_payload={
            "answer": "external provider response",
            "debug": "token=sk-" + "wave113",
        },
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="provider-external-http-client-closed",
    )
