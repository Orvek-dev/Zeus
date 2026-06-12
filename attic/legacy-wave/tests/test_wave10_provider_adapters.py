from __future__ import annotations

import json
from datetime import timedelta
from typing import ClassVar

import pytest

import zeus_agent.model_runtime.provider_registry as provider_registry_module
from zeus_agent.model_runtime.provider_registry import ProviderRegistry
from zeus_agent.model_runtime.provider_boundary import (
    ProviderBoundaryRequest,
    ProviderRawToolCall,
)
from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderUsage,
)
from zeus_agent.runtime_lease import RuntimeLease, RuntimeLeaseIntakeResult
from zeus_agent.transport_runtime import (
    AuthorityRequirement,
    SandboxProbeDefinition,
    TransportAdapterManifest,
    TransportHealth,
    TransportKind,
    TransportPolicy,
    TransportRegistry,
)

EVIDENCE_TARGET = "mneme.wave10.provider_runtime"


def test_happy_adapter_routing_when_lease_allows_provider_kinds() -> None:
    # Given: one dry-run lease covering every Wave10 provider capability.
    registry = ProviderRegistry()
    lease = _lease(
        capabilities=(
            "provider.fake.generate",
            "provider.local.generate",
            "provider.external.generate",
        ),
    )

    # When: each provider kind is routed through the registry.
    fake = registry.generate(_request("fake"), lease, now=lease.issued_at)
    local = registry.generate(_request("local_llm"), lease, now=lease.issued_at)
    openai = registry.generate(
        _request("openai_compatible", credential_scope="external.openai.readonly"),
        lease,
        now=lease.issued_at,
    )
    anthropic = registry.generate(
        _request("anthropic_metadata", credential_scope="external.anthropic.readonly"),
        lease,
        now=lease.issued_at,
    )

    # Then: deterministic adapters return dry-run outputs with no side effects.
    assert fake.decision == "selected"
    assert fake.content == "fake provider dry-run response"
    assert local.decision == "selected"
    assert local.metadata_value("local.endpoint") == "http://127.0.0.1:11434"
    assert openai.decision == "dry_run"
    assert openai.tool_calls[0].call_id == "call_weather_001"
    assert openai.tool_calls[0].arguments_as_dict()["location"] == "Seoul"
    assert anthropic.decision == "dry_run"
    assert anthropic.metadata_value("anthropic.tool_use_id") == "toolu_01weather"
    assert all(
        response.handler_executed is False
        and response.network_opened is False
        and response.sdk_imported is False
        and response.credential_material_accessed is False
        for response in (fake, local, openai, anthropic)
    )


def test_lease_boundary_blocks_missing_malformed_and_expired_leases() -> None:
    # Given: a provider request and a deterministic lease fixture.
    registry = ProviderRegistry()
    lease = _lease(capabilities=("provider.fake.generate",))
    request = _request("fake")

    # When: no usable RuntimeLease is supplied.
    missing = registry.generate(request, None)
    malformed = registry.generate(request, object())
    expired = registry.generate(request, lease, now=lease.expires_at + timedelta(seconds=1))

    # Then: every case fails before adapter execution.
    assert _blocked_reason(missing) == "missing_runtime_lease"
    assert _blocked_reason(malformed) == "malformed_runtime_lease"
    assert _blocked_reason(expired) == "runtime_lease_expired"
    assert missing.handler_executed is False
    assert malformed.handler_executed is False
    assert expired.handler_executed is False


def test_external_provider_blocks_missing_and_secret_credential_scope() -> None:
    # Given: external provider authority without raw credential material access.
    registry = ProviderRegistry()
    raw_secret = "sk-wave10-secret-value"
    lease = _lease(capabilities=("provider.external.generate",))

    # When: external-style requests omit credentials or supply secret-like input.
    missing = registry.generate(_request("openai_compatible"), lease, now=lease.issued_at)
    secret = registry.generate(
        _request("openai_compatible", credential_scope=raw_secret),
        lease,
        now=lease.issued_at,
    )

    # Then: both block and serialized results never echo the raw secret.
    serialized = json.dumps(secret.model_dump(mode="json"), sort_keys=True)
    assert _blocked_reason(missing) == "missing_credential_scope"
    assert _blocked_reason(secret) == "unsafe_credential"
    assert raw_secret not in serialized
    assert secret.credential_material_accessed is False


def test_live_network_and_metadata_authority_claims_do_not_bypass_lease() -> None:
    # Given: a dry-run external lease and metadata that claims provider authority.
    registry = ProviderRegistry()
    lease = _lease(capabilities=("provider.external.generate",))
    metadata = (
        ProviderMetadataEntry(key="authority.claimed_capability", value="provider.external.generate"),
        ProviderMetadataEntry(key="authority.claimed_live_network", value="true"),
    )

    # When: live network is requested without live lease posture.
    live = registry.generate(
        _request(
            "openai_compatible",
            credential_scope="external.openai.readonly",
            live_network=True,
            metadata=metadata,
        ),
        lease,
        now=lease.issued_at,
    )

    # Then: metadata remains non-authority and live transport stays blocked.
    assert _blocked_reason(live) == "live_network_without_scope"
    assert live.network_opened is False

    # Given: a lease lacking the external provider capability.
    fake_only_lease = _lease(capabilities=("provider.fake.generate",), credential_scopes=())

    # When: metadata tries to claim external provider capability.
    bypass = registry.generate(
        _request("openai_compatible", credential_scope="external.openai.readonly", metadata=metadata),
        fake_only_lease,
        now=fake_only_lease.issued_at,
    )

    # Then: provider metadata cannot grant authority.
    assert _blocked_reason(bypass) == "authority_widening"


def test_fallback_over_budget_and_transport_mismatch_stay_blocked() -> None:
    # Given: a registry with fallback configured and a mismatched transport manifest.
    lease = _lease(capabilities=("provider.fake.generate", "provider.external.generate"))
    registry = ProviderRegistry(transport_registry=_mismatched_transport_registry())

    # When: the primary provider blocks, fallback is not selected.
    fallback = registry.generate(
        _request("openai_compatible"),
        lease,
        fallback_provider_kind="fake",
        now=lease.issued_at,
    )
    over_budget = ProviderRegistry().generate(
        _request("fake"),
        lease,
        budget_required=lease.budget_limit + 1,
        now=lease.issued_at,
    )
    mismatch = registry.generate(_request("fake"), lease, now=lease.issued_at)

    # Then: no blocked provider silently falls through to another adapter.
    assert _blocked_reason(fallback) == "missing_credential_scope"
    assert fallback.provider_kind == "openai_compatible"
    assert _blocked_reason(over_budget) == "over_budget"
    assert _blocked_reason(mismatch) == "transport_kind_mismatch"


def test_untrusted_boundary_blocks_unknown_provider_and_malformed_tool_json() -> None:
    # Given: untrusted provider input that has not become a typed runtime request yet.
    registry = ProviderRegistry()
    lease = _lease(capabilities=("provider.external.generate",))
    unknown = ProviderBoundaryRequest(
        provider_kind="unknown_provider",
        provider_id="unknown.provider",
        model_id="unknown.model",
        messages=(ProviderMessage(role="user", content="invalid provider"),),
    )
    malformed_tool = ProviderBoundaryRequest(
        provider_kind="openai_compatible",
        provider_id="openai_compatible.provider",
        model_id="openai_compatible.model",
        messages=(ProviderMessage(role="user", content="invalid tool args"),),
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

    # When: the registry inspects the boundary before adapter selection.
    unknown_result = registry.inspect_untrusted(unknown, lease, now=lease.issued_at)
    malformed_result = registry.inspect_untrusted(malformed_tool, lease, now=lease.issued_at)

    # Then: both fail closed without adapter, client, SDK, or network execution.
    assert unknown_result.decision == "blocked"
    assert unknown_result.reason == "unsupported_provider"
    assert malformed_result.decision == "blocked"
    assert malformed_result.reason == "malformed_tool_arguments"
    assert unknown_result.adapter_invoked is False
    assert malformed_result.adapter_invoked is False
    assert unknown_result.client_constructed is False
    assert malformed_result.client_constructed is False
    assert unknown_result.network_opened is False
    assert malformed_result.network_opened is False


def test_untrusted_boundary_rejections_do_not_construct_or_invoke_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: adapter classes that record construction and invocation.
    _RecordingProviderRuntime.constructed = []
    _RecordingProviderRuntime.invoked = []
    monkeypatch.setattr(provider_registry_module, "FakeProviderRuntime", _RecordingFakeProviderRuntime)
    monkeypatch.setattr(provider_registry_module, "LocalLLMProviderRuntime", _RecordingLocalProviderRuntime)
    monkeypatch.setattr(
        provider_registry_module,
        "OpenAICompatibleProviderRuntime",
        _RecordingOpenAIProviderRuntime,
    )
    monkeypatch.setattr(
        provider_registry_module,
        "AnthropicMetadataProviderRuntime",
        _RecordingAnthropicProviderRuntime,
    )
    registry = ProviderRegistry()
    lease = _lease(capabilities=("provider.external.generate",))
    unknown = ProviderBoundaryRequest(
        provider_kind="unknown_provider",
        provider_id="unknown.provider",
        model_id="unknown.model",
        messages=(ProviderMessage(role="user", content="invalid provider"),),
    )
    malformed_tool = ProviderBoundaryRequest(
        provider_kind="openai_compatible",
        provider_id="openai_compatible.provider",
        model_id="openai_compatible.model",
        messages=(ProviderMessage(role="user", content="invalid tool args"),),
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

    # When: rejected untrusted requests are inspected.
    unknown_result = registry.inspect_untrusted(unknown, lease, now=lease.issued_at)
    malformed_result = registry.inspect_untrusted(malformed_tool, lease, now=lease.issued_at)

    # Then: rejection happened before adapter construction or invocation.
    assert unknown_result.reason == "unsupported_provider"
    assert malformed_result.reason == "malformed_tool_arguments"
    assert _RecordingProviderRuntime.constructed == []
    assert _RecordingProviderRuntime.invoked == []
    assert unknown_result.adapter_invoked is False
    assert malformed_result.adapter_invoked is False
    assert unknown_result.client_constructed is False
    assert malformed_result.client_constructed is False


class _RecordingProviderRuntime:
    constructed: ClassVar[list[str]] = []
    invoked: ClassVar[list[str]] = []

    provider_kind: str

    def __init__(self, provider_kind: str) -> None:
        self.provider_kind = provider_kind
        self.constructed.append(provider_kind)

    def generate(
        self,
        request: ProviderRuntimeRequest,
        authorization: RuntimeLeaseIntakeResult,
    ) -> ProviderRuntimeResponse:
        self.invoked.append(self.provider_kind)
        return ProviderRuntimeResponse(
            decision="dry_run",
            provider_kind=request.provider_kind,
            provider_id=request.provider_id,
            model_id=request.model_id,
            response_id="resp_recording_provider",
            content="recorded dry run",
            usage=ProviderUsage(input_tokens=0, output_tokens=0, budget_units=0, latency_ms=0),
        )


class _RecordingFakeProviderRuntime(_RecordingProviderRuntime):
    def __init__(self) -> None:
        super().__init__("fake")


class _RecordingLocalProviderRuntime(_RecordingProviderRuntime):
    def __init__(self) -> None:
        super().__init__("local_llm")


class _RecordingOpenAIProviderRuntime(_RecordingProviderRuntime):
    def __init__(self) -> None:
        super().__init__("openai_compatible")


class _RecordingAnthropicProviderRuntime(_RecordingProviderRuntime):
    def __init__(self) -> None:
        super().__init__("anthropic_metadata")


def _request(
    provider_kind: str,
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
        messages=(ProviderMessage(role="user", content="Draft a Wave10 dry-run response."),),
        credential_scope=credential_scope,
        network_host=network_host,
        live_network=live_network,
        metadata=metadata,
    )


def _lease(
    *,
    capabilities: tuple[str, ...],
    credential_scopes: tuple[str, ...] = (
        "external.openai.readonly",
        "external.anthropic.readonly",
    ),
) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave10.lease.provider",
        objective_id="wave10.objective.provider_runtime",
        principal_id="wave10.principal.worker_b",
        run_id="wave10.run.provider_adapters",
        allowed_capabilities=capabilities,
        credential_scopes=credential_scopes,
        network_hosts=("api.openai.local",),
        budget_limit=100,
        evidence_target=EVIDENCE_TARGET,
    )


def _mismatched_transport_registry() -> TransportRegistry:
    registry = TransportRegistry()
    registry.register(
        TransportAdapterManifest(
            transport_id="wave10.transport.fake_mismatch",
            kind=TransportKind.mcp,
            display_name="Wrong-kind fake provider transport",
            capability_id="provider.fake.generate",
            policy=TransportPolicy(
                policy_labels=("dry_run",),
                authority_requirements=(
                    AuthorityRequirement(capability_id="provider.fake.generate"),
                ),
            ),
        )
    )
    registry.run_probe(
        SandboxProbeDefinition(
            probe_id="wave10.probe.fake_mismatch",
            transport_id="wave10.transport.fake_mismatch",
            expected_health=TransportHealth.healthy,
        )
    )
    return registry


def _blocked_reason(response: ProviderRuntimeResponse) -> str | None:
    return response.metadata_value("block.reason")
