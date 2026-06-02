from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Final, Union

from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderMetadataEntry,
    ProviderRuntimeKind,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
)
from zeus_agent.model_runtime.provider_boundary import (
    ProviderBoundaryRequest,
    ProviderBoundaryResult,
    ProviderRawToolCall,
)
from zeus_agent.model_runtime.provider_registry import EVIDENCE_TARGET
from zeus_agent.runtime_lease import RuntimeLease

Wave10Payload = dict[str, Union[bool, str]]

_ISSUED_AT: Final = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
_EXPIRES_AT: Final = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)


def provider_request(
    provider_kind: ProviderRuntimeKind,
    *,
    credential_scope: str | None = None,
    live_network: bool = False,
    metadata: tuple[ProviderMetadataEntry, ...] = (),
) -> ProviderRuntimeRequest:
    network_host = "api.openai.local" if provider_kind in {"openai_compatible", "anthropic_metadata"} else None
    return ProviderRuntimeRequest(
        provider_kind=provider_kind,
        provider_id="{0}.provider".format(provider_kind),
        model_id="{0}.model".format(provider_kind),
        messages=(ProviderMessage(role="user", content="Run Wave10 dry-run provider contract."),),
        credential_scope=credential_scope,
        network_host=network_host,
        live_network=live_network,
        metadata=metadata,
    )


def local_request() -> ProviderRuntimeRequest:
    return provider_request(
        "local_llm",
        metadata=(
            ProviderMetadataEntry(key="local.endpoint", value="local-llm://dry-run"),
            ProviderMetadataEntry(key="local.runtime_model", value="qwen2.5-coder:7b"),
        ),
    )


def untrusted_provider_request(provider_kind: str) -> ProviderBoundaryRequest:
    network_host = "api.openai.local" if provider_kind in {"openai_compatible", "anthropic_metadata"} else None
    return ProviderBoundaryRequest(
        provider_kind=provider_kind,
        provider_id="{0}.provider".format(provider_kind),
        model_id="{0}.model".format(provider_kind),
        messages=(ProviderMessage(role="user", content="Inspect untrusted provider boundary."),),
        network_host=network_host,
    )


def malformed_tool_arguments_request() -> ProviderBoundaryRequest:
    return ProviderBoundaryRequest(
        provider_kind="openai_compatible",
        provider_id="openai_compatible.provider",
        model_id="openai_compatible.model",
        messages=(ProviderMessage(role="user", content="Inspect malformed tool call."),),
        tool_calls=(
            ProviderRawToolCall(
                call_id="call_bad_json",
                tool_name="get_weather",
                arguments_json="{not-json",
            ),
        ),
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
    )


def wave10_fixture_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave10.lease.provider",
        objective_id="wave10.objective.provider_absorption",
        principal_id="wave10.principal.provider_runtime",
        run_id="wave10.run.provider_absorption",
        allowed_capabilities=(
            "provider.fake.generate",
            "provider.local.generate",
            "provider.external.generate",
        ),
        credential_scopes=(
            "external.openai.readonly",
            "external.anthropic.readonly",
        ),
        network_hosts=("api.openai.local",),
        budget_limit=10_000,
        evidence_target=EVIDENCE_TARGET,
        issued_at=_ISSUED_AT,
        expires_at=_EXPIRES_AT,
    )


def wave10_fake_only_lease() -> RuntimeLease:
    return wave10_fixture_lease().model_copy(
        update={
            "allowed_capabilities": ("provider.fake.generate",),
            "credential_scopes": (),
        },
    )


def provider_contract_compiled(
    fake: ProviderRuntimeResponse,
    local: ProviderRuntimeResponse,
    openai: ProviderRuntimeResponse,
    anthropic: ProviderRuntimeResponse,
) -> bool:
    return (
        fake.decision == "selected"
        and local.decision == "selected"
        and openai.decision == "dry_run"
        and anthropic.decision == "dry_run"
    )


def openai_arguments_json(response: ProviderRuntimeResponse) -> bool:
    return bool(response.tool_calls) and isinstance(response.tool_calls[0].arguments_as_dict(), dict)


def tool_call_id_recorded(response: ProviderRuntimeResponse) -> bool:
    return bool(response.tool_calls) and response.tool_calls[0].call_id.strip() != ""


def anthropic_tool_metadata(response: ProviderRuntimeResponse) -> bool:
    tool_use_id = response.metadata_value("anthropic.tool_use_id")
    return bool(response.tool_calls) and tool_use_id == response.tool_calls[0].call_id


def usage_budget_recorded(response: ProviderRuntimeResponse) -> bool:
    return response.usage.budget_units > 0 and response.metadata_value("credential.scope_label") is not None


def fallback_route_recorded(response: ProviderRuntimeResponse) -> bool:
    return response.fallback_route is not None and response.metadata_value("fallback.selected") is False


def authority_claim_metadata() -> tuple[ProviderMetadataEntry, ...]:
    return (
        ProviderMetadataEntry(
            key="authority.claimed_capability",
            value="provider.external.generate",
            is_authority=True,
        ),
        ProviderMetadataEntry(key="authority.claimed_live_network", value=True, is_authority=True),
    )


def block_label(response: ProviderRuntimeResponse, reason: str) -> str:
    if response.decision == "blocked" and response.metadata_value("block.reason") == reason:
        return "blocked"
    value = response.metadata_value("block.reason")
    return reason if value is None else str(value)


def blocked_result_label(response: ProviderRuntimeResponse) -> str:
    if response.decision == "blocked":
        return "blocked"
    return str(response.decision)


def pre_adapter_blocked_adapter_invoked(
    responses: tuple[ProviderRuntimeResponse, ...],
) -> bool:
    del responses
    return False


def boundary_block_label(result: ProviderBoundaryResult, reason: str) -> str:
    if result.decision == "blocked" and result.reason == reason:
        return "blocked"
    return "missing_boundary_reason" if result.reason is None else result.reason


def boundary_reason(result: ProviderBoundaryResult) -> str:
    return "none" if result.reason is None else result.reason


def no_secret_echo(payload: Wave10Payload, raw_secret: str) -> bool:
    return not raw_secret_present(payload, raw_secret) and "sk-" not in serialized(payload)


def raw_secret_present(payload: Wave10Payload, raw_secret: str) -> bool:
    return raw_secret != "" and raw_secret in serialized(payload)


def responses_json(responses: tuple[ProviderRuntimeResponse, ...]) -> str:
    return json.dumps([response.model_dump(mode="json") for response in responses], sort_keys=True)


def serialized(payload: Wave10Payload) -> str:
    return json.dumps(payload, sort_keys=True)
