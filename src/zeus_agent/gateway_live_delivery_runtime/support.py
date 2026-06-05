from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterRuntime
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from zeus_agent.runtime_lease import RuntimeLease

NOW: Final = datetime(2026, 6, 6, 3, 0, tzinfo=timezone.utc)
EXPIRES_AT: Final = datetime(2026, 6, 7, 3, 0, tzinfo=timezone.utc)
ADAPTER_ID: Final = "slack"
ALLOWLISTED_TARGET: Final = "slack://ops"
GATEWAY_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "external_delivery",
)
GATEWAY_LIVE_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "external_delivery",
    "live_transport",
)


def configure_gateway(home: Path):
    settings = GatewaySettingsRuntime(home).add(
        adapter_ref=ADAPTER_ID,
        target=ALLOWLISTED_TARGET,
    )
    pairing = GatewayPairingRuntime(home).pair(
        adapter_id=ADAPTER_ID,
        target=ALLOWLISTED_TARGET,
        proof_ref="pairing://rc4/slack/ops",
    )
    pairings = GatewayPairingRuntime(home).list()
    return settings, pairing, pairings


def build_transport_lease(*, network_host: str):
    return LiveTransportLeaseRuntime().bind(
        readiness=gateway_readiness(),
        lease=RuntimeLease(
            lease_id="rc4.lease.gateway",
            objective_id="rc4.objective.gateway",
            principal_id="rc4.principal.operator",
            run_id="rc4.run.gateway",
            allowed_capabilities=("gateway.slack.dispatch",),
            credential_scopes=("external.gateway.readonly",),
            network_hosts=(network_host,),
            budget_limit=100,
            evidence_target="mneme.rc4.gateway_live_delivery",
            live_transport_allowed=True,
            issued_at=NOW,
            expires_at=EXPIRES_AT,
        ),
        runtime_kind="gateway",
        capability_id="gateway.slack.dispatch",
        credential_scope="external.gateway.readonly",
        network_host=network_host,
        budget_required=1,
        evidence_target="mneme.rc4.gateway_live_delivery",
        now=NOW,
    )


def build_adapter_plan(envelope: LiveGatewayDeliveryResult):
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="gateway",
        envelope=envelope.to_payload(),
        operator_proof=operator_proof(reviewed_risks=GATEWAY_RISKS),
        required_risks=GATEWAY_RISKS,
    )
    release = LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="gateway",
        release_ref="executor-release://rc4/gateway-live-delivery",
        idempotency_key="rc4-gateway-live-delivery-release",
    )
    return LiveGatewayAdapterRuntime().plan(
        release=release,
        gateway_envelope=envelope,
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=0,
        idempotency_key="rc4-gateway-live-delivery-adapter",
    )


def build_activation(adapter_plan):
    opt_in = LiveTransportOptInRuntime().record(
        adapter_kind="gateway",
        adapter_plan=adapter_plan,
        operator_proof=operator_proof(reviewed_risks=GATEWAY_LIVE_RISKS),
        opt_in_ref="live-opt-in://rc4/gateway-live-delivery",
        requested_transport_mode="live",
    )
    return LiveTransportActivationRuntime().plan(
        opt_in=opt_in,
        adapter_kind="gateway",
        adapter_plan=adapter_plan,
        activation_ref="live-activation://rc4/gateway-live-delivery",
    )


def gateway_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="rc4.readiness.gateway",
        execution_plan_id="live-execute-plan-rc4-gateway",
        handoff_manifest_id="live-handoff-rc4-gateway",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.slack.dispatch",
        credential_bindings_ready=True,
        gateway_pairing_ready=True,
        secret_resolver_ready=True,
        operator_proof_bound=True,
        blocked_reasons=(),
        gate_summary={
            "credential_bindings_ready": True,
            "gateway_pairing_ready": True,
            "gateway_paired_target_count": 1,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        operator_proof_summary={
            "proof_id": "rc4.proof.operator",
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
        proof_id="rc4.proof.operator",
        operator_id="rc4.operator",
        execution_plan_id="live-execute-plan-rc4-gateway",
        proof_ref="operator-proof://rc4/gateway-live-delivery",
        reviewed_risks=reviewed_risks,
    )
