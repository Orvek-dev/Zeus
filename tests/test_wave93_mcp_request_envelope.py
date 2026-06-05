from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.runtime_lease import RuntimeLease


def test_mcp_request_envelope_blocks_without_transport_lease() -> None:
    result = LiveMcpRequestRuntime().prepare(
        transport_lease=None,
        secret_material=None,
        server_id="mcp.github",
        tool_name="repo.search",
        endpoint="https://mcp.github.local/rpc",
        arguments={"query": "Zeus"},
    )

    assert result.decision == "blocked"
    assert "transport_lease_required" in result.blocked_reasons
    assert result.request_prepared is False
    assert result.server_started is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_mcp_request_envelope_prepares_remote_tool_without_starting_server(monkeypatch) -> None:
    material = "mcp-" + "material-value"
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", material)

    result = LiveMcpRequestRuntime().prepare(
        transport_lease=_mcp_transport_lease(),
        secret_material=_secret_material(),
        server_id="mcp.github",
        tool_name="repo.search",
        endpoint="https://mcp.github.local/rpc",
        arguments={"query": "Zeus"},
    )

    payload = result.to_payload()
    assert result.decision == "prepared"
    assert result.request_prepared is True
    assert result.secret_material_verified is True
    assert result.endpoint_host == "mcp.github.local"
    assert result.tool_allowlisted is True
    assert result.server_started is False
    assert result.resources_enabled is False
    assert result.prompts_enabled is False
    assert result.tool_invoked is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert material not in json.dumps(payload)


def test_mcp_request_envelope_blocks_endpoint_outside_transport_lease(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")

    result = LiveMcpRequestRuntime().prepare(
        transport_lease=_mcp_transport_lease(),
        secret_material=_secret_material(),
        server_id="mcp.github",
        tool_name="repo.search",
        endpoint="https://evil.local/rpc",
        arguments={"query": "Zeus"},
    )

    assert result.decision == "blocked"
    assert "mcp_endpoint_not_lease_bound" in result.blocked_reasons
    assert result.request_prepared is False
    assert result.network_opened is False


def test_cli_and_python_library_mcp_request_envelope(monkeypatch) -> None:
    material = "mcp-" + "material-value"
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", material)
    transport_lease = _mcp_transport_lease()
    secret_material = _secret_material()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-mcp-request-envelope",
            "--transport-lease-json",
            transport_lease.model_dump_json(),
            "--secret-material-json",
            secret_material.model_dump_json(),
            "--server-id",
            "mcp.github",
            "--tool-name",
            "repo.search",
            "--endpoint",
            "https://mcp.github.local/rpc",
            "--arguments-json",
            json.dumps({"query": "Zeus"}),
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "prepared"
    assert payload["server_started"] is False
    assert material not in completed.stdout

    library_payload = ZeusAgent().live_mcp_request_envelope(
        transport_lease.to_payload(),
        secret_material.to_payload(),
        server_id="mcp.github",
        tool_name="repo.search",
        endpoint="https://mcp.github.local/rpc",
        arguments={"query": "Zeus"},
    )
    assert library_payload["decision"] == "prepared"
    assert library_payload["tool_invoked"] is False


def _mcp_transport_lease():
    return LiveTransportLeaseRuntime().bind(
        readiness=_remote_mcp_readiness(),
        lease=_mcp_lease(),
        runtime_kind="mcp",
        capability_id="mcp.github.repo.search",
        credential_scope="external.github.readonly",
        network_host="mcp.github.local",
        budget_required=1,
        evidence_target="mneme.wave93.mcp_request",
        now=_now(),
    )


def _secret_material():
    return LiveSecretMaterialRuntime().check(
        transport_lease=_mcp_transport_lease(),
        secret_ref="env://ZEUS_W93_GITHUB_TOKEN",
        allow_material_access=True,
    )


def _remote_mcp_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="wave93.readiness.mcp",
        execution_plan_id="live-execute-plan-wave93",
        handoff_manifest_id="live-handoff-wave93",
        surface_kind="mcp",
        surface_id="mcp.github",
        capability_id="mcp.github.repo.search",
        credential_bindings_ready=True,
        gateway_pairing_ready=True,
        secret_resolver_ready=True,
        operator_proof_bound=True,
        blocked_reasons=(),
        gate_summary={
            "credential_bindings_ready": True,
            "gateway_pairing_ready": True,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        operator_proof_summary={
            "proof_id": "wave93.proof.operator",
            "operator_reviewed": True,
            "execution_authorized": False,
        },
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )


def _mcp_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave93.lease.mcp",
        objective_id="wave93.objective.live",
        principal_id="wave93.principal.operator",
        run_id="wave93.run.live",
        allowed_capabilities=("mcp.github.repo.search",),
        credential_scopes=("external.github.readonly",),
        network_hosts=("mcp.github.local",),
        budget_limit=100,
        evidence_target="mneme.wave93.mcp_request",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 6, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
