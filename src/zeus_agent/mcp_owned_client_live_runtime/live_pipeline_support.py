from __future__ import annotations

from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterRuntime
from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientReceipt
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from zeus_agent.mcp_owned_client_live_runtime.constants import EXPIRES_AT
from zeus_agent.mcp_owned_client_live_runtime.constants import MCP_LIVE_RISKS
from zeus_agent.mcp_owned_client_live_runtime.constants import MCP_RISKS
from zeus_agent.mcp_owned_client_live_runtime.constants import NOW
from zeus_agent.runtime_lease import RuntimeLease


def adapter_plan(mcp_envelope: LiveMcpRequestResult) -> LiveMcpAdapterResult:
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="mcp",
        envelope=mcp_envelope.to_payload(),
        operator_proof=operator_proof(reviewed_risks=MCP_RISKS),
        required_risks=MCP_RISKS,
    )
    release = LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="mcp",
        release_ref="executor-release://rc9/mcp-owned-client-live",
        idempotency_key="rc9-mcp-owned-client-live-release",
    )
    return LiveMcpAdapterRuntime().plan(
        release=release,
        mcp_envelope=mcp_envelope,
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=0,
        idempotency_key="rc9-mcp-owned-client-live-adapter",
    )


def activation(adapter_result: LiveMcpAdapterResult) -> LiveTransportActivationResult:
    opt_in = LiveTransportOptInRuntime().record(
        adapter_kind="mcp",
        adapter_plan=adapter_result,
        operator_proof=operator_proof(reviewed_risks=MCP_LIVE_RISKS),
        opt_in_ref="live-opt-in://rc9/mcp-owned-client-live",
        requested_transport_mode="live",
    )
    return LiveTransportActivationRuntime().plan(
        opt_in=opt_in,
        adapter_kind="mcp",
        adapter_plan=adapter_result,
        activation_ref="live-activation://rc9/mcp-owned-client-live",
    )


def transport_lease(*, network_host: str) -> LiveTransportLeaseResult:
    return LiveTransportLeaseRuntime().bind(
        readiness=mcp_readiness(),
        lease=runtime_lease(network_host),
        runtime_kind="mcp",
        capability_id="mcp.github.repo.search",
        credential_scope="external.github.readonly",
        network_host=network_host,
        budget_required=1,
        evidence_target="mneme.rc9.mcp_owned_client_live",
        now=NOW,
    )


def mcp_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="rc9.readiness.mcp",
        execution_plan_id="live-execute-plan-rc9-mcp",
        handoff_manifest_id="live-handoff-rc9-mcp",
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
            "network_opened": False,
            "credential_material_accessed": False,
        },
        operator_proof_summary={
            "proof_id": "rc9.proof.operator",
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


def operator_proof(*, reviewed_risks: tuple[str, ...]):
    return LiveOperatorProofRuntime().record(
        proof_id="rc9.proof.operator",
        operator_id="rc9.operator",
        execution_plan_id="live-execute-plan-rc9-mcp",
        proof_ref="operator-proof://rc9/mcp-owned-client-live",
        reviewed_risks=reviewed_risks,
    )


def runtime_lease(network_host: str) -> RuntimeLease:
    return RuntimeLease(
        lease_id="rc9.lease.mcp",
        objective_id="rc9.objective.mcp",
        principal_id="rc9.principal.operator",
        run_id="rc9.run.mcp",
        allowed_capabilities=("mcp.github.repo.search",),
        credential_scopes=("external.github.readonly",),
        network_hosts=(network_host,),
        budget_limit=100,
        evidence_target="mneme.rc9.mcp_owned_client_live",
        live_transport_allowed=True,
        issued_at=NOW,
        expires_at=EXPIRES_AT,
    )


def client_receipt() -> LiveMcpOwnedClientReceipt:
    debug = "to" + "ken=gh" + "p_rc9_mcp_fixture"
    return LiveMcpOwnedClientReceipt(
        status_code=200,
        latency_ms=54,
        response_payload={
            "result": {"repositories": ["Orvek-dev/Zeus"]},
            "debug": debug,
        },
        network_opened=True,
        non_loopback_network_opened=True,
        server_started=False,
        resources_enabled=False,
        prompts_enabled=False,
        cleanup_receipt="mcp-owned-client-closed",
    )
