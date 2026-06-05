from __future__ import annotations

from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientTransportRuntime
from zeus_agent.live_mcp_owned_client_transport_runtime import StaticMcpOwnedClient
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffRuntime
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.mcp_owned_client_live_runtime.contract import endpoint_allowlisted
from zeus_agent.mcp_owned_client_live_runtime.contract import endpoint_host
from zeus_agent.mcp_owned_client_live_runtime.contract import make_contract
from zeus_agent.mcp_owned_client_live_runtime.live_pipeline_support import activation
from zeus_agent.mcp_owned_client_live_runtime.live_pipeline_support import adapter_plan
from zeus_agent.mcp_owned_client_live_runtime.live_pipeline_support import client_receipt
from zeus_agent.mcp_owned_client_live_runtime.live_pipeline_support import transport_lease
from zeus_agent.mcp_owned_client_live_runtime.models import McpOwnedClientLiveContract
from zeus_agent.mcp_owned_client_live_runtime.models import McpOwnedClientLiveScenario


def build_owned_client_smoke_contract(
    *,
    scenario: McpOwnedClientLiveScenario,
    endpoint: str,
    allowed_host: str,
    secret_ref: str,
    server_id: str,
    tool_name: str,
    query: str,
) -> McpOwnedClientLiveContract:
    host = endpoint_host(endpoint)
    allowlisted = endpoint_allowlisted(endpoint, (allowed_host,))
    if host is None:
        return make_contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("malformed_mcp_endpoint",),
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
            mcp_owned_client_smoke={
                "transport_lease": lease.to_payload(),
                "secret_material": secret_material.to_payload(),
            },
        )

    mcp_envelope = LiveMcpRequestRuntime().prepare(
        transport_lease=lease,
        secret_material=secret_material,
        server_id=server_id,
        tool_name=tool_name,
        endpoint=endpoint,
        arguments={"query": query},
    )
    adapter_result = adapter_plan(mcp_envelope)
    activation_result = activation(adapter_result)
    policy = LiveRemoteTransportPolicyRuntime().plan(
        activation=activation_result,
        adapter_kind="mcp",
        adapter_plan=adapter_result,
        transport_kind="remote_server",
        remote_target=endpoint,
        allowed_remote_targets=(allowed_host,),
        credential_scope="external.github.readonly",
        credential_binding_ref=f"credential-binding://external.github.readonly@{host}",
        policy_ref="remote-policy://rc9/mcp-owned-client-live",
        audit_ref="live-audit://rc9/mcp-owned-client-live",
        redaction_ref="live-response://rc9/mcp-owned-client-live",
        teardown_ref="teardown://rc9/mcp-owned-client-live",
        production_review_ref="review://rc9/mcp-owned-client-live",
    )
    handoff = LiveRemoteCredentialHandoffRuntime().prepare(
        policy=policy,
        secret_material=secret_material,
        handoff_ref="credential-handoff://rc9/mcp-owned-client-live",
        auth_scheme="bearer",
        header_name="Authorization",
    )
    preflight = LiveRemoteExecutorPreflightRuntime().plan(
        policy=policy,
        handoff=handoff,
        executor_kind="mcp",
        executor_ref="remote-executor://rc9/mcp-owned-client-live",
        idempotency_key="rc9-mcp-owned-client-live",
        teardown_ref=policy.teardown_ref or "",
        timeout_ms=1500,
        retry_attempts=1,
    )
    owned_client_transport = LiveMcpOwnedClientTransportRuntime().execute(
        policy=policy,
        preflight=preflight,
        handoff=handoff,
        mcp_envelope=mcp_envelope,
        client=StaticMcpOwnedClient(client_receipt()),
        execution_ref="mcp-owned-client://rc9/mcp-owned-client-live",
    )
    audit = LiveTransportAuditRuntime().audit(
        adapter_kind="mcp",
        execution=owned_client_transport,
        audit_ref="live-audit://rc9/mcp-owned-client-live",
    )
    redaction = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload=owned_client_transport.redacted_response or {},
        response_ref="live-response://rc9/mcp-owned-client-live",
    )
    ready = (
        owned_client_transport.decision == "executed"
        and audit.decision == "audit_ready"
        and redaction.decision == "redacted"
        and owned_client_transport.non_loopback_network_opened
        and not owned_client_transport.server_started
        and not owned_client_transport.resources_enabled
        and not owned_client_transport.prompts_enabled
        and not owned_client_transport.live_production_claimed
    )
    return make_contract(
        decision="report" if ready else "blocked",
        scenario=scenario,
        blocked_reasons=() if ready else _blocked_reasons(policy, preflight, owned_client_transport),
        mcp_owned_client_live_ready=ready,
        operator_live_opted_in=True,
        endpoint_allowlisted=True,
        secret_material_available=secret_material.material_available,
        mcp_owned_client_smoke={
            "transport_lease": lease.to_payload(),
            "secret_material": secret_material.to_payload(),
            "mcp_envelope": mcp_envelope.to_payload(),
            "adapter_plan": adapter_result.to_payload(),
            "activation": activation_result.to_payload(),
            "policy": policy.to_payload(),
            "handoff": handoff.to_payload(),
            "preflight": preflight.to_payload(),
            "mcp_owned_client_transport": owned_client_transport.to_payload(),
            "audit": audit.to_payload(),
            "redaction": redaction.to_payload(),
        },
        network_opened=owned_client_transport.network_opened,
        non_loopback_network_opened=owned_client_transport.non_loopback_network_opened,
        controlled_external_side_effects=owned_client_transport.controlled_external_side_effects,
        tool_invoked=owned_client_transport.tool_invoked,
        handler_executed=owned_client_transport.handler_executed,
        credential_material_accessed=secret_material.credential_material_accessed,
        material_released=handoff.material_released,
        server_started=owned_client_transport.server_started,
        resources_enabled=owned_client_transport.resources_enabled,
        prompts_enabled=owned_client_transport.prompts_enabled,
    )


def _blocked_reasons(*items) -> tuple[str, ...]:
    reasons: list[str] = []
    for item in items:
        reasons.extend(item.blocked_reasons)
    return tuple(dict.fromkeys(reasons))
