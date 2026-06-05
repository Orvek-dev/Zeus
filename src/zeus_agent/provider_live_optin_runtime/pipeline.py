from __future__ import annotations

from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalTransportRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffRuntime
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.provider_live_optin_runtime.contract import endpoint_allowlisted
from zeus_agent.provider_live_optin_runtime.contract import endpoint_host
from zeus_agent.provider_live_optin_runtime.contract import make_contract
from zeus_agent.provider_live_optin_runtime.live_pipeline_support import activation
from zeus_agent.provider_live_optin_runtime.live_pipeline_support import adapter_plan
from zeus_agent.provider_live_optin_runtime.live_pipeline_support import client_receipt
from zeus_agent.provider_live_optin_runtime.live_pipeline_support import transport_lease
from zeus_agent.provider_live_optin_runtime.models import ProviderLiveOptinContract
from zeus_agent.provider_live_optin_runtime.models import ProviderLiveOptinScenario


def build_external_receipt_contract(
    *,
    scenario: ProviderLiveOptinScenario,
    endpoint: str,
    allowed_host: str,
    secret_ref: str,
    model_id: str,
    message: str,
) -> ProviderLiveOptinContract:
    host = endpoint_host(endpoint)
    allowlisted = endpoint_allowlisted(endpoint, (allowed_host,))
    if host is None:
        return make_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("malformed_provider_endpoint",),
            operator_live_opted_in=True,
        )
    if not allowlisted:
        return make_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("remote_target_not_allowlisted",),
            operator_live_opted_in=True,
        )

    lease = transport_lease(network_host=host)
    secret_material = LiveSecretMaterialRuntime().check(
        transport_lease=lease,
        secret_ref=secret_ref,
        allow_material_access=True,
    )
    if secret_material.decision != "available":
        return make_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=secret_material.blocked_reasons,
            operator_live_opted_in=True,
            endpoint_allowlisted=True,
            credential_material_accessed=secret_material.credential_material_accessed,
            external_smoke={
                "transport_lease": lease.to_payload(),
                "secret_material": secret_material.to_payload(),
            },
        )

    provider_envelope = LiveProviderRequestRuntime().prepare(
        transport_lease=lease,
        secret_material=secret_material,
        provider_kind="openai_compatible",
        model_id=model_id,
        endpoint=endpoint,
        message=message,
    )
    adapter_result = adapter_plan(provider_envelope)
    activation_result = activation(adapter_result)
    policy = LiveRemoteTransportPolicyRuntime().plan(
        activation=activation_result,
        adapter_kind="provider",
        adapter_plan=adapter_result,
        transport_kind="external_http",
        remote_target=endpoint,
        allowed_remote_targets=(allowed_host,),
        credential_scope="external.openai.readonly",
        credential_binding_ref=f"credential-binding://external.openai.readonly@{host}",
        policy_ref="remote-policy://rc7/provider-live-optin",
        audit_ref="live-audit://rc7/provider-live-optin",
        redaction_ref="live-response://rc7/provider-live-optin",
        teardown_ref="teardown://rc7/provider-live-optin",
        production_review_ref="review://rc7/provider-live-optin",
    )
    handoff = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=policy,
        secret_material=secret_material,
        handoff_ref="credential-handoff://rc7/provider-live-optin",
        auth_scheme="bearer",
        header_name="Authorization",
    )
    preflight = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="provider",
        executor_ref="remote-executor://rc7/provider-live-optin",
        idempotency_key="rc7-provider-live-optin",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )
    external_transport = LiveProviderExternalTransportRuntime().execute(
        policy=policy,
        preflight=preflight,
        provider_envelope=provider_envelope,
        client_result=client_receipt(),
        execution_ref="provider-external://rc7/provider-live-optin",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=external_transport,
        audit_ref="live-audit://rc7/provider-live-optin",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=external_transport.redacted_response or {},
        response_ref="live-response://rc7/provider-live-optin",
    )
    ready = (
        external_transport.decision == "executed"
        and audit.decision == "audit_ready"
        and redaction.decision == "redacted"
        and external_transport.non_loopback_network_opened
        and not external_transport.live_production_claimed
    )
    return make_contract(
        decision="report" if ready else "blocked",
        scenario=scenario,
        blocked_reasons=() if ready else _blocked_reasons(policy, preflight, external_transport),
        provider_live_optin_ready=ready,
        operator_live_opted_in=True,
        endpoint_allowlisted=True,
        secret_material_available=secret_material.material_available,
        external_smoke={
            "transport_lease": lease.to_payload(),
            "secret_material": secret_material.to_payload(),
            "provider_envelope": provider_envelope.to_payload(),
            "adapter_plan": adapter_result.to_payload(),
            "activation": activation_result.to_payload(),
            "policy": policy.to_payload(),
            "handoff": handoff.to_payload(),
            "preflight": preflight.to_payload(),
            "external_transport": external_transport.to_payload(),
            "audit": audit.to_payload(),
            "redaction": redaction.to_payload(),
        },
        network_opened=external_transport.network_opened,
        non_loopback_network_opened=external_transport.non_loopback_network_opened,
        controlled_external_side_effects=external_transport.controlled_external_side_effects,
        provider_invoked=external_transport.provider_invoked,
        handler_executed=external_transport.handler_executed,
        credential_material_accessed=secret_material.credential_material_accessed,
        material_released=handoff.material_released,
    )


def _blocked_reasons(*items) -> tuple[str, ...]:
    reasons: list[str] = []
    for item in items:
        reasons.extend(item.blocked_reasons)
    return tuple(dict.fromkeys(reasons))
