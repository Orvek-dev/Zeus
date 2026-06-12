from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
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
from zeus_agent.loopback_provider_http_server import LoopbackProviderHttpServer

ProviderLiveApiDecision = Literal["report", "blocked"]
ProviderLiveApiScenario = Literal["status", "loopback-smoke"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_TARGET_VERSION: Final = "v1.0.0-rc.2"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.2.provider_live_api"
_NOW: Final = datetime(2026, 6, 6, 1, 0, tzinfo=timezone.utc)
_EXPIRES_AT: Final = datetime(2026, 6, 7, 1, 0, tzinfo=timezone.utc)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)
_PROVIDER_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "external_provider_inference",
)
_PROVIDER_LIVE_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "external_provider_inference",
    "live_transport",
)


class ProviderLiveApiContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ProviderLiveApiDecision
    target_version: str
    release_stage: Literal["provider_live_api"]
    objective_contract_id: str
    scenario: ProviderLiveApiScenario
    blocked_reasons: tuple[str, ...] = ()
    provider_live_api_contract_available: bool = True
    provider_loopback_http_available: bool = True
    provider_credentialed_http_available: bool = True
    provider_external_transport_available: bool = False
    provider_owned_client_available: bool = True
    provider_direct_adapter_available: bool = True
    provider_live_api_ready: bool = False
    production_ready: bool = False
    loopback_smoke: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_external_side_effects: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> ProviderLiveApiContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_provider_live_api_contract(
    *,
    scenario: str = "status",
    secret_ref: str = "env://ZEUS_RC2_PROVIDER_KEY",
    message: str = "summarize provider live api checkpoint",
) -> ProviderLiveApiContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in {"status", "loopback-smoke"}:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_provider_live_api_scenario",),
        )
    if safe_scenario == "status":
        return _contract(decision="report", scenario="status")
    return _loopback_smoke(secret_ref=secret_ref, message=message)


def _loopback_smoke(*, secret_ref: str, message: str) -> ProviderLiveApiContract:
    transport_lease = _transport_lease(network_host="127.0.0.1")
    secret_material = LiveSecretMaterialRuntime().check(
        transport_lease=transport_lease,
        secret_ref=secret_ref,
        allow_material_access=True,
    )
    if secret_material.decision != "available":
        return _contract(
            decision="blocked",
            scenario="loopback-smoke",
            blocked_reasons=secret_material.blocked_reasons,
            loopback_smoke={
                "transport_lease": transport_lease.to_payload(),
                "secret_material": secret_material.to_payload(),
            },
            credential_material_accessed=secret_material.credential_material_accessed,
        )

    server = LoopbackProviderHttpServer()
    server.start()
    try:
        endpoint = "{0}/v1/chat/completions".format(server.base_url)
        provider_envelope = LiveProviderRequestRuntime().prepare(
            transport_lease=transport_lease,
            secret_material=secret_material,
            provider_kind="openai_compatible",
            model_id="gpt-rc2-loopback",
            endpoint=endpoint,
            message=message,
        )
        adapter_plan = _adapter_plan(provider_envelope)
        activation = _activation(adapter_plan)
        execution = LiveProviderHttpTransportRuntime().execute(
            activation=activation,
            adapter_plan=adapter_plan,
            provider_envelope=provider_envelope,
            transport_kind="local_http",
            execution_ref="provider-live-api://rc2/loopback",
        )
        audit = LiveTransportAuditRuntime().audit(
            adapter_kind="provider",
            execution=execution,
            audit_ref="live-audit://rc2/provider-live-api",
        )
        redaction = LiveResponseRedactionRuntime().redact(
            audit=audit,
            response_payload=execution.redacted_response or {},
            response_ref="live-response://rc2/provider-live-api",
        )
    finally:
        server.shutdown()

    ready = (
        execution.decision == "executed"
        and audit.decision == "audit_ready"
        and redaction.decision == "redacted"
        and server.shutdown_complete
        and execution.non_loopback_network_opened is False
        and execution.live_production_claimed is False
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="loopback-smoke",
        blocked_reasons=() if ready else tuple(execution.blocked_reasons or audit.blocked_reasons),
        loopback_smoke={
            "transport_lease": transport_lease.to_payload(),
            "secret_material": secret_material.to_payload(),
            "provider_envelope": provider_envelope.to_payload(),
            "adapter_plan": adapter_plan.to_payload(),
            "activation": activation.to_payload(),
            "execution": execution.to_payload(),
            "audit": audit.to_payload(),
            "redaction": redaction.to_payload(),
            "server_request_count": server.request_count("/v1/chat/completions"),
            "server_shutdown_complete": server.shutdown_complete,
        },
        provider_live_api_ready=ready,
        network_opened=execution.network_opened,
        non_loopback_network_opened=execution.non_loopback_network_opened,
        handler_executed=execution.handler_executed,
        credential_material_accessed=secret_material.credential_material_accessed,
    )


def _contract(
    *,
    decision: ProviderLiveApiDecision,
    scenario: ProviderLiveApiScenario,
    blocked_reasons: tuple[str, ...] = (),
    loopback_smoke: Optional[dict[str, JsonValue]] = None,
    provider_live_api_ready: bool = False,
    network_opened: bool = False,
    non_loopback_network_opened: bool = False,
    handler_executed: bool = False,
    credential_material_accessed: bool = False,
) -> ProviderLiveApiContract:
    result = ProviderLiveApiContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="provider_live_api",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        loopback_smoke=loopback_smoke,
        provider_live_api_ready=provider_live_api_ready,
        production_ready=False,
        network_opened=network_opened,
        non_loopback_network_opened=non_loopback_network_opened,
        controlled_external_side_effects=False,
        handler_executed=handler_executed,
        external_delivery_opened=False,
        credential_material_accessed=credential_material_accessed,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _adapter_plan(provider_envelope):
    authorization = LiveExecutionAuthorizationRuntime().authorize(
        envelope_kind="provider",
        envelope=provider_envelope.to_payload(),
        operator_proof=_operator_proof(reviewed_risks=_PROVIDER_RISKS),
        required_risks=_PROVIDER_RISKS,
    )
    release = LiveExecutorReleaseRuntime().release(
        authorization=authorization,
        executor_kind="provider",
        release_ref="executor-release://rc2/provider-live-api",
        idempotency_key="rc2-provider-live-api-release",
    )
    return LiveProviderAdapterRuntime().plan(
        release=release,
        provider_envelope=provider_envelope,
        transport_mode="dry_run",
        timeout_ms=1500,
        retry_attempts=0,
        idempotency_key="rc2-provider-live-api-adapter",
    )


def _activation(adapter_plan):
    opt_in = LiveTransportOptInRuntime().record(
        adapter_kind="provider",
        adapter_plan=adapter_plan,
        operator_proof=_operator_proof(reviewed_risks=_PROVIDER_LIVE_RISKS),
        opt_in_ref="live-opt-in://rc2/provider-live-api",
        requested_transport_mode="live",
    )
    return LiveTransportActivationRuntime().plan(
        opt_in=opt_in,
        adapter_kind="provider",
        adapter_plan=adapter_plan,
        activation_ref="live-activation://rc2/provider-live-api",
    )


def _transport_lease(*, network_host: str):
    return LiveTransportLeaseRuntime().bind(
        readiness=_provider_readiness(),
        lease=_runtime_lease(network_host),
        runtime_kind="provider",
        capability_id="provider.external.generate",
        credential_scope="external.openai.readonly",
        network_host=network_host,
        budget_required=1,
        evidence_target="mneme.rc2.provider_live_api",
        now=_NOW,
    )


def _provider_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="rc2.readiness.provider",
        execution_plan_id="live-execute-plan-rc2-provider",
        handoff_manifest_id="live-handoff-rc2-provider",
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
            "gateway_pairing_ready": True,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        operator_proof_summary={
            "proof_id": "rc2.proof.operator",
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


def _operator_proof(*, reviewed_risks: tuple[str, ...]):
    return LiveOperatorProofRuntime().record(
        proof_id="rc2.proof.operator",
        operator_id="rc2.operator",
        execution_plan_id="live-execute-plan-rc2-provider",
        proof_ref="operator-proof://rc2/provider-live-api",
        reviewed_risks=reviewed_risks,
    )


def _runtime_lease(network_host: str) -> RuntimeLease:
    return RuntimeLease(
        lease_id="rc2.lease.provider",
        objective_id="rc2.objective.provider",
        principal_id="rc2.principal.operator",
        run_id="rc2.run.provider",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=(network_host,),
        budget_limit=100,
        evidence_target="mneme.rc2.provider_live_api",
        live_transport_allowed=True,
        issued_at=_NOW,
        expires_at=_EXPIRES_AT,
    )
