from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterRuntime
from zeus_agent.live_provider_http_transport_runtime import LiveProviderHttpTransportRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer
from tests.test_wave86_live_provider_execution import _provider_readiness


def test_provider_http_transport_blocks_non_loopback_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    envelope = _provider_envelope("https://api.openai.local/v1/chat/completions", "api.openai.local")

    result = LiveProviderHttpTransportRuntime().execute(
        activation=_activation(envelope),
        adapter_plan=_adapter_plan(envelope),
        provider_envelope=envelope,
        transport_kind="local_http",
        execution_ref="provider-http://wave107/non-loopback",
    )

    assert result.decision == "blocked"
    assert "provider_http_endpoint_not_loopback" in result.blocked_reasons
    assert result.provider_invoked is False
    assert result.network_opened is False
    assert result.non_loopback_network_opened is False
    assert result.live_production_claimed is False


def test_provider_http_transport_executes_loopback_with_audit_and_redaction(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        envelope = _provider_envelope("{0}/v1/chat/completions".format(server.base_url), "127.0.0.1")
        result = LiveProviderHttpTransportRuntime().execute(
            activation=_activation(envelope),
            adapter_plan=_adapter_plan(envelope),
            provider_envelope=envelope,
            transport_kind="local_http",
            execution_ref="provider-http://wave107/provider",
        )
        audit = LiveTransportAuditRuntime().audit(
            adapter_kind="provider",
            execution=result,
            audit_ref="live-audit://wave107/provider-http",
        )
        redaction = LiveResponseRedactionRuntime().redact(
            audit=audit,
            response_payload=result.redacted_response or {},
            response_ref="live-response://wave107/provider-http",
        )
    finally:
        server.shutdown()

    assert result.decision == "executed"
    assert result.local_http_loopback is True
    assert result.provider_invoked is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.handler_executed is True
    assert result.cleanup_receipt == "provider-local-http-client-closed"
    assert server.request_count("/v1/chat/completions") == 1
    assert audit.decision == "audit_ready"
    assert audit.external_side_effects_absent is True
    assert redaction.decision == "redacted"
    assert redaction.no_secret_echo is True
    assert result.live_production_claimed is False
    assert server.shutdown_complete is True


def test_provider_http_transport_blocks_malformed_response(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        envelope = _provider_envelope("{0}/malformed".format(server.base_url), "127.0.0.1")
        result = LiveProviderHttpTransportRuntime().execute(
            activation=_activation(envelope),
            adapter_plan=_adapter_plan(envelope),
            provider_envelope=envelope,
            transport_kind="local_http",
            execution_ref="provider-http://wave107/malformed",
        )
    finally:
        server.shutdown()

    assert result.decision == "blocked"
    assert "provider_http_response_not_json_object" in result.blocked_reasons
    assert result.network_opened is True
    assert result.handler_executed is False
    assert server.request_count("/malformed") == 1


def test_cli_and_python_library_provider_http_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        envelope = _provider_envelope("{0}/v1/chat/completions".format(server.base_url), "127.0.0.1")
        activation = _activation(envelope)
        adapter_plan = _adapter_plan(envelope)
        runner = CliRunner()

        completed = runner.invoke(
            app,
            [
                "live-provider-http-transport",
                "--activation-json",
                activation.model_dump_json(),
                "--adapter-plan-json",
                adapter_plan.model_dump_json(),
                "--provider-envelope-json",
                envelope.model_dump_json(),
                "--transport-kind",
                "local_http",
                "--execution-ref",
                "provider-http://wave107/provider",
                "--json",
            ],
        )
        library_payload = ZeusAgent().live_provider_http_transport(
            activation.to_payload(),
            adapter_plan=adapter_plan.to_payload(),
            provider_envelope=envelope.to_payload(),
            transport_kind="local_http",
            execution_ref="provider-http://wave107/provider-library",
        )
    finally:
        server.shutdown()

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"
    assert server.request_count("/v1/chat/completions") == 2


def _provider_envelope(endpoint: str, network_host: str):
    return LiveProviderRequestRuntime().prepare(
        transport_lease=_transport_lease(network_host),
        secret_material=_secret_material(network_host),
        provider_kind="openai_compatible",
        model_id="gpt-wave107",
        endpoint=endpoint,
        message="summarize local transport state",
    )


def _adapter_plan(provider_envelope):
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="provider",
        envelope=provider_envelope.to_payload(),
        operator_proof=_operator_proof(),
        required_risks=("network", "credential_material_access", "external_provider_inference"),
    )
    release = LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="provider",
        release_ref="executor-release://wave107/provider",
        idempotency_key="wave107-provider-release-1",
    )
    return LiveProviderAdapterRuntime().plan(
        release=release,
        provider_envelope=provider_envelope,
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=0,
        idempotency_key="wave107-provider-http-1",
    )


def _activation(provider_envelope):
    adapter_plan = _adapter_plan(provider_envelope)
    opt_in = LiveTransportOptInRuntime().record(
        adapter_kind="provider",
        adapter_plan=adapter_plan,
        operator_proof=_operator_proof(
            ("network", "credential_material_access", "external_provider_inference", "live_transport")
        ),
        opt_in_ref="live-opt-in://wave107/provider",
        requested_transport_mode="live",
    )
    return LiveTransportActivationRuntime().plan(
        opt_in=opt_in,
        adapter_kind="provider",
        adapter_plan=adapter_plan,
        activation_ref="live-activation://wave107/provider",
    )


def _transport_lease(network_host: str):
    return LiveTransportLeaseRuntime().bind(
        readiness=_provider_readiness(),
        lease=_runtime_lease(network_host),
        runtime_kind="provider",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host=network_host,
        budget_required=1,
        evidence_target="mneme.wave107.provider_http",
        now=_now(),
    )


def _secret_material(network_host: str):
    return LiveSecretMaterialRuntime().check(
        transport_lease=_transport_lease(network_host),
        secret_ref="env://ZEUS_W107_OPENAI_KEY",
        allow_material_access=True,
    )


def _operator_proof(
    reviewed_risks: tuple[str, ...] = (
        "network",
        "credential_material_access",
        "external_provider_inference",
    ),
):
    return LiveOperatorProofRuntime().record(
        proof_id="wave107.proof.operator",
        operator_id="wave107.operator",
        execution_plan_id="live-execute-plan-wave107",
        proof_ref="operator-proof://wave107/review",
        reviewed_risks=reviewed_risks,
    )


def _runtime_lease(network_host: str) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave107.lease.provider",
        objective_id="wave107.objective.live",
        principal_id="wave107.principal.operator",
        run_id="wave107.run.live",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=(network_host,),
        budget_limit=100,
        evidence_target="mneme.wave107.provider_http",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 6, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
