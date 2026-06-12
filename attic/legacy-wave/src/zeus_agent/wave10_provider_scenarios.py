from __future__ import annotations

from zeus_agent.model_runtime.provider_registry import ProviderRegistry
from zeus_agent.runtime_lease import RuntimeIntakeRequest, RuntimeLeaseBuilder
from zeus_agent.wave10_provider_support import (
    Wave10Payload,
    anthropic_tool_metadata,
    authority_claim_metadata,
    boundary_block_label,
    boundary_reason,
    block_label,
    blocked_result_label,
    fallback_route_recorded,
    local_request,
    malformed_tool_arguments_request,
    no_secret_echo,
    openai_arguments_json,
    pre_adapter_blocked_adapter_invoked,
    provider_contract_compiled,
    provider_request,
    raw_secret_present,
    responses_json,
    tool_call_id_recorded,
    untrusted_provider_request,
    usage_budget_recorded,
    wave10_fake_only_lease,
    wave10_fixture_lease,
)


def wave10_provider_happy_payload() -> Wave10Payload:
    lease = wave10_fixture_lease()
    registry = ProviderRegistry()
    fake = registry.generate(provider_request("fake"), lease, now=lease.issued_at)
    local = registry.generate(local_request(), lease, now=lease.issued_at)
    openai = registry.generate(
        provider_request("openai_compatible", credential_scope="external.openai.readonly"),
        lease,
        now=lease.issued_at,
    )
    anthropic = registry.generate(
        provider_request("anthropic_metadata", credential_scope="external.anthropic.readonly"),
        lease,
        now=lease.issued_at,
    )
    fallback = registry.generate(
        provider_request("openai_compatible"),
        lease,
        fallback_provider_kind="fake",
        now=lease.issued_at,
    )
    responses = (fake, local, openai, anthropic, fallback)
    payload: Wave10Payload = {
        "scenario_id": "C001",
        "provider_contract_compiled": provider_contract_compiled(fake, local, openai, anthropic),
        "fake_provider": fake.decision,
        "local_llm_provider": local.decision,
        "openai_compatible_provider": openai.decision,
        "anthropic_metadata_provider": anthropic.decision,
        "openai_arguments_json": openai_arguments_json(openai),
        "tool_call_id_recorded": tool_call_id_recorded(openai),
        "anthropic_tool_use_metadata": anthropic_tool_metadata(anthropic),
        "local_endpoint_metadata": local.metadata_value("local.endpoint") == "local-llm://dry-run",
        "usage_budget_recorded": usage_budget_recorded(openai),
        "fallback_route_recorded": fallback_route_recorded(fallback),
        "runtime_lease_validated": provider_contract_compiled(fake, local, openai, anthropic),
        "handler_executed": any(response.handler_executed for response in responses),
        "network_opened": any(response.network_opened for response in responses),
        "sdk_imported": any(response.sdk_imported for response in responses),
        "credential_material_accessed": any(
            response.credential_material_accessed for response in responses
        ),
    }
    return payload | {"no_secret_echo": no_secret_echo(payload, "")}


def wave10_provider_blocks_payload(raw_secret: str) -> Wave10Payload:
    lease = wave10_fixture_lease()
    registry = ProviderRegistry()
    openai = provider_request("openai_compatible", credential_scope="external.openai.readonly")
    missing = registry.generate(openai, None)
    malformed = registry.generate(openai, object())
    expired = registry.generate(openai, lease, now=lease.expires_at)
    missing_credential = registry.generate(provider_request("openai_compatible"), lease, now=lease.issued_at)
    unsafe_credential = registry.generate(
        provider_request("openai_compatible", credential_scope=raw_secret),
        lease,
        now=lease.issued_at,
    )
    live_network = registry.generate(
        provider_request(
            "openai_compatible",
            credential_scope="external.openai.readonly",
            live_network=True,
        ),
        lease,
        now=lease.issued_at,
    )
    metadata_bypass = registry.generate(
        provider_request(
            "openai_compatible",
            credential_scope="external.openai.readonly",
            metadata=authority_claim_metadata(),
        ),
        wave10_fake_only_lease(),
        now=lease.issued_at,
    )
    fallback = registry.generate(
        provider_request("openai_compatible"),
        lease,
        fallback_provider_kind="fake",
        now=lease.issued_at,
    )
    over_budget = registry.generate(
        provider_request("fake"),
        lease,
        budget_required=lease.budget_limit + 1,
        now=lease.issued_at,
    )
    unknown_provider = registry.inspect_untrusted(
        untrusted_provider_request("unknown_provider"),
        lease,
        now=lease.issued_at,
    )
    malformed_tool_arguments = registry.inspect_untrusted(
        malformed_tool_arguments_request(),
        lease,
        now=lease.issued_at,
    )
    kind_mismatch = RuntimeLeaseBuilder().authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="mcp.echo",
            budget_required=1,
            evidence_target=lease.evidence_target,
        ),
        now=lease.issued_at,
    )
    blocked_responses = (
        missing,
        malformed,
        expired,
        missing_credential,
        unsafe_credential,
        live_network,
        metadata_bypass,
        fallback,
        over_budget,
    )
    payload: Wave10Payload = {
        "scenario_id": "C002",
        "missing_runtime_lease": block_label(missing, "missing_runtime_lease"),
        "malformed_runtime_lease": block_label(malformed, "malformed_runtime_lease"),
        "expired_runtime_lease": block_label(expired, "runtime_lease_expired"),
        "runtime_kind_capability_mismatch": "blocked"
        if kind_mismatch.reason == "runtime_kind_capability_mismatch"
        else kind_mismatch.reason,
        "missing_credential_scope": block_label(missing_credential, "missing_credential_scope"),
        "unsafe_credential": block_label(unsafe_credential, "unsafe_credential"),
        "live_network_without_scope": block_label(live_network, "live_network_without_scope"),
        "metadata_authority_bypass": blocked_result_label(metadata_bypass),
        "fallback_after_block": blocked_result_label(fallback),
        "unknown_provider": boundary_block_label(unknown_provider, "unsupported_provider"),
        "unknown_provider_reason": boundary_reason(unknown_provider),
        "malformed_tool_arguments": boundary_block_label(
            malformed_tool_arguments,
            "malformed_tool_arguments",
        ),
        "malformed_tool_arguments_reason": boundary_reason(malformed_tool_arguments),
        "over_budget": block_label(over_budget, "over_budget"),
        "handler_executed": any(response.handler_executed for response in blocked_responses)
        or unknown_provider.handler_executed
        or malformed_tool_arguments.handler_executed,
        "adapter_invoked": pre_adapter_blocked_adapter_invoked(blocked_responses)
        or unknown_provider.adapter_invoked
        or malformed_tool_arguments.adapter_invoked,
        "client_constructed": unknown_provider.client_constructed
        or malformed_tool_arguments.client_constructed,
        "network_opened": any(response.network_opened for response in blocked_responses)
        or unknown_provider.network_opened
        or malformed_tool_arguments.network_opened,
        "sdk_imported": any(response.sdk_imported for response in blocked_responses)
        or unknown_provider.sdk_imported
        or malformed_tool_arguments.sdk_imported,
        "credential_material_accessed": any(
            response.credential_material_accessed for response in blocked_responses
        )
        or unknown_provider.credential_material_accessed
        or malformed_tool_arguments.credential_material_accessed,
    }
    secret_present = raw_secret_present(payload, raw_secret) or raw_secret in responses_json(
        blocked_responses,
    )
    return payload | {
        "no_secret_echo": not secret_present,
        "raw_secret_present": secret_present,
    }
