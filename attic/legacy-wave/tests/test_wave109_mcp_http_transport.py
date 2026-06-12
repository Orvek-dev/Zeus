from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterRuntime
from zeus_agent.live_mcp_http_transport_runtime import LiveMcpHttpTransportRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer
from tests.test_wave93_mcp_request_envelope import _remote_mcp_readiness


def test_mcp_http_transport_blocks_non_loopback_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    envelope = _mcp_envelope("https://mcp.github.local/rpc", "mcp.github.local")

    result = LiveMcpHttpTransportRuntime().execute(
        activation=_activation(envelope),
        adapter_plan=_adapter_plan(envelope),
        mcp_envelope=envelope,
        transport_kind="local_http",
        execution_ref="mcp-http://wave109/non-loopback",
    )

    assert result.decision == "blocked"
    assert "mcp_http_endpoint_not_loopback" in result.blocked_reasons
    assert result.tool_invoked is False
    assert result.network_opened is False
    assert result.server_started is False


def test_mcp_http_transport_executes_loopback_with_audit_and_redaction(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        envelope = _mcp_envelope("{0}/v1/chat/completions".format(server.base_url), "127.0.0.1")
        result = LiveMcpHttpTransportRuntime().execute(
            activation=_activation(envelope),
            adapter_plan=_adapter_plan(envelope),
            mcp_envelope=envelope,
            transport_kind="local_http",
            execution_ref="mcp-http://wave109/mcp",
        )
        audit = LiveTransportAuditRuntime().audit(
            adapter_kind="mcp",
            execution=result,
            audit_ref="live-audit://wave109/mcp-http",
        )
        redaction = LiveResponseRedactionRuntime().redact(
            audit=audit,
            response_payload=result.redacted_response or {},
            response_ref="live-response://wave109/mcp-http",
        )
    finally:
        server.shutdown()

    assert result.decision == "executed"
    assert result.local_http_loopback is True
    assert result.tool_invoked is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is False
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.cleanup_receipt == "mcp-local-http-client-closed"
    assert server.request_count("/v1/chat/completions") == 1
    assert audit.decision == "audit_ready"
    assert redaction.decision == "redacted"
    assert result.live_production_claimed is False


def test_mcp_http_transport_blocks_malformed_response(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        envelope = _mcp_envelope("{0}/malformed".format(server.base_url), "127.0.0.1")
        result = LiveMcpHttpTransportRuntime().execute(
            activation=_activation(envelope),
            adapter_plan=_adapter_plan(envelope),
            mcp_envelope=envelope,
            transport_kind="local_http",
            execution_ref="mcp-http://wave109/malformed",
        )
    finally:
        server.shutdown()

    assert result.decision == "blocked"
    assert "mcp_http_response_not_json_object" in result.blocked_reasons
    assert result.network_opened is True
    assert result.handler_executed is False
    assert server.request_count("/malformed") == 1


def test_cli_and_python_library_mcp_http_transport(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        envelope = _mcp_envelope("{0}/v1/chat/completions".format(server.base_url), "127.0.0.1")
        activation = _activation(envelope)
        adapter_plan = _adapter_plan(envelope)
        completed = CliRunner().invoke(
            app,
            [
                "live-mcp-http-transport",
                "--activation-json",
                activation.model_dump_json(),
                "--adapter-plan-json",
                adapter_plan.model_dump_json(),
                "--mcp-envelope-json",
                envelope.model_dump_json(),
                "--transport-kind",
                "local_http",
                "--execution-ref",
                "mcp-http://wave109/mcp",
                "--json",
            ],
        )
        library_payload = ZeusAgent().live_mcp_http_transport(
            activation.to_payload(),
            adapter_plan=adapter_plan.to_payload(),
            mcp_envelope=envelope.to_payload(),
            transport_kind="local_http",
            execution_ref="mcp-http://wave109/mcp-library",
        )
    finally:
        server.shutdown()

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["server_started"] is False
    assert payload["network_opened"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"
    assert server.request_count("/v1/chat/completions") == 2


def _mcp_envelope(endpoint: str, network_host: str):
    return LiveMcpRequestRuntime().prepare(
        transport_lease=_transport_lease(network_host),
        secret_material=_secret_material(network_host),
        server_id="mcp.github",
        tool_name="repo.search",
        endpoint=endpoint,
        arguments={"query": "Zeus"},
    )


def _adapter_plan(mcp_envelope):
    risks = ("network", "credential_material_access", "mcp_remote_tool")
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="mcp",
        envelope=mcp_envelope.to_payload(),
        operator_proof=_operator_proof(risks),
        required_risks=risks,
    )
    release = LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="mcp",
        release_ref="executor-release://wave109/mcp",
        idempotency_key="wave109-mcp-release-1",
    )
    return LiveMcpAdapterRuntime().plan(
        release=release,
        mcp_envelope=mcp_envelope,
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=0,
        idempotency_key="wave109-mcp-http-1",
    )


def _activation(mcp_envelope):
    adapter_plan = _adapter_plan(mcp_envelope)
    opt_in = LiveTransportOptInRuntime().record(
        adapter_kind="mcp",
        adapter_plan=adapter_plan,
        operator_proof=_operator_proof(("network", "credential_material_access", "mcp_remote_tool", "live_transport")),
        opt_in_ref="live-opt-in://wave109/mcp",
        requested_transport_mode="live",
    )
    return LiveTransportActivationRuntime().plan(
        opt_in=opt_in,
        adapter_kind="mcp",
        adapter_plan=adapter_plan,
        activation_ref="live-activation://wave109/mcp",
    )


def _transport_lease(network_host: str):
    return LiveTransportLeaseRuntime().bind(
        readiness=_remote_mcp_readiness(),
        lease=_runtime_lease(network_host),
        runtime_kind="mcp",
        capability_id="mcp.github.repo.search",
        credential_scope="external.github.readonly",
        network_host=network_host,
        budget_required=1,
        evidence_target="mneme.wave109.mcp_http",
        now=_now(),
    )


def _secret_material(network_host: str):
    return LiveSecretMaterialRuntime().check(
        transport_lease=_transport_lease(network_host),
        secret_ref="env://ZEUS_W109_GITHUB_TOKEN",
        allow_material_access=True,
    )


def _operator_proof(reviewed_risks: tuple[str, ...]):
    return LiveOperatorProofRuntime().record(
        proof_id="wave109.proof.operator",
        operator_id="wave109.operator",
        execution_plan_id="live-execute-plan-wave109",
        proof_ref="operator-proof://wave109/review",
        reviewed_risks=reviewed_risks,
    )


def _runtime_lease(network_host: str) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave109.lease.mcp",
        objective_id="wave109.objective.live",
        principal_id="wave109.principal.operator",
        run_id="wave109.run.live",
        allowed_capabilities=("mcp.github.repo.search",),
        credential_scopes=("external.github.readonly",),
        network_hosts=(network_host,),
        budget_limit=100,
        evidence_target="mneme.wave109.mcp_http",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 6, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
