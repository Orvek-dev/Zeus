from __future__ import annotations

from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterRuntime
from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalClientResult
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from zeus_agent.provider_live_optin_runtime.constants import EXPIRES_AT
from zeus_agent.provider_live_optin_runtime.constants import NOW
from zeus_agent.provider_live_optin_runtime.constants import PROVIDER_LIVE_RISKS
from zeus_agent.provider_live_optin_runtime.constants import PROVIDER_RISKS
from zeus_agent.runtime_lease import RuntimeLease


def adapter_plan(provider_envelope: LiveProviderRequestResult) -> LiveProviderAdapterResult:
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="provider",
        envelope=provider_envelope.to_payload(),
        operator_proof=operator_proof(reviewed_risks=PROVIDER_RISKS),
        required_risks=PROVIDER_RISKS,
    )
    release = LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="provider",
        release_ref="executor-release://rc7/provider-live-optin",
        idempotency_key="rc7-provider-live-optin-release",
    )
    return LiveProviderAdapterRuntime().plan(
        release=release,
        provider_envelope=provider_envelope,
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=0,
        idempotency_key="rc7-provider-live-optin-adapter",
    )


def activation(adapter_result: LiveProviderAdapterResult) -> LiveTransportActivationResult:
    opt_in = LiveTransportOptInRuntime().record(
        adapter_kind="provider",
        adapter_plan=adapter_result,
        operator_proof=operator_proof(reviewed_risks=PROVIDER_LIVE_RISKS),
        opt_in_ref="live-opt-in://rc7/provider-live-optin",
        requested_transport_mode="live",
    )
    return LiveTransportActivationRuntime().plan(
        opt_in=opt_in,
        adapter_kind="provider",
        adapter_plan=adapter_result,
        activation_ref="live-activation://rc7/provider-live-optin",
    )


def transport_lease(*, network_host: str) -> LiveTransportLeaseResult:
    return LiveTransportLeaseRuntime().bind(
        readiness=provider_readiness(),
        lease=runtime_lease(network_host),
        runtime_kind="provider",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host=network_host,
        budget_required=1,
        evidence_target="mneme.rc7.provider_live_optin",
        now=NOW,
    )


def provider_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="rc7.readiness.provider",
        execution_plan_id="live-execute-plan-rc7-provider",
        handoff_manifest_id="live-handoff-rc7-provider",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
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
            "proof_id": "rc7.proof.operator",
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
        proof_id="rc7.proof.operator",
        operator_id="rc7.operator",
        execution_plan_id="live-execute-plan-rc7-provider",
        proof_ref="operator-proof://rc7/provider-live-optin",
        reviewed_risks=reviewed_risks,
    )


def runtime_lease(network_host: str) -> RuntimeLease:
    return RuntimeLease(
        lease_id="rc7.lease.provider",
        objective_id="rc7.objective.provider",
        principal_id="rc7.principal.operator",
        run_id="rc7.run.provider",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=(network_host,),
        budget_limit=100,
        evidence_target="mneme.rc7.provider_live_optin",
        live_transport_allowed=True,
        issued_at=NOW,
        expires_at=EXPIRES_AT,
    )


def client_receipt() -> LiveProviderExternalClientResult:
    debug = "to" + "ken=s" + "k-rc7-provider-fixture"
    return LiveProviderExternalClientResult(
        status_code=200,
        latency_ms=42,
        response_payload={
            "answer": "external provider receipt",
            "debug": debug,
        },
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="provider-external-http-client-closed",
    )
