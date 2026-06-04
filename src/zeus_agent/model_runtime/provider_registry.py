from __future__ import annotations

from datetime import datetime
from typing import Callable, Final, Protocol

from pydantic import ValidationError

from zeus_agent.model_runtime.anthropic_metadata_provider import (
    AnthropicMetadataProviderRuntime,
)
from zeus_agent.model_runtime.fake_provider import FakeProviderRuntime
from zeus_agent.model_runtime.interfaces import (
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderToolCall,
)
from zeus_agent.model_runtime.local_llm_provider import LocalLLMProviderRuntime
from zeus_agent.model_runtime.openai_compatible_provider import (
    OpenAICompatibleProviderRuntime,
)
from zeus_agent.model_runtime.provider_boundary import (
    ProviderBoundaryRequest,
    ProviderBoundaryResult,
)
from zeus_agent.model_runtime.provider_responses import (
    blocked_boundary_result,
    blocked_provider_response,
    boundary_result_from_response,
)
from zeus_agent.runtime_lease import (
    RuntimeIntakeRequest,
    RuntimeLease,
    RuntimeLeaseBuilder,
    RuntimeLeaseIntakeResult,
)
from zeus_agent.transport_runtime import (
    TransportExecutionGate,
    TransportExecutionGateRequest,
    TransportKind,
    TransportRegistry,
)

EVIDENCE_TARGET: Final = "mneme.wave10.provider_runtime"
_EXTERNAL_KINDS: Final = {"openai_compatible", "anthropic_metadata"}
_CAPABILITY_IDS: Final = {
    "fake": "provider.fake.generate",
    "local_llm": "provider.local.generate",
    "openai_compatible": "provider.external.generate",
    "anthropic_metadata": "provider.external.generate",
}


class ProviderAdapter(Protocol):
    def generate(
        self,
        request: ProviderRuntimeRequest,
        authorization: RuntimeLeaseIntakeResult,
    ) -> ProviderRuntimeResponse:
        ...


ProviderAdapterFactory = Callable[[], ProviderAdapter]


class ProviderRegistry:
    def __init__(self, transport_registry: TransportRegistry | None = None) -> None:
        self._adapter_factories: dict[str, ProviderAdapterFactory] = {
            "fake": FakeProviderRuntime,
            "local_llm": LocalLLMProviderRuntime,
            "openai_compatible": OpenAICompatibleProviderRuntime,
            "anthropic_metadata": AnthropicMetadataProviderRuntime,
        }
        self._adapters: dict[str, ProviderAdapter] = {}
        self._adapter_invocations: dict[str, int] = {}
        self._transport_gate = (
            TransportExecutionGate(transport_registry)
            if transport_registry is not None
            else None
        )
        self._lease_builder = RuntimeLeaseBuilder()

    def generate(
        self,
        request: ProviderRuntimeRequest,
        lease: RuntimeLease | None,
        *,
        fallback_provider_kind: str | None = None,
        budget_required: int = 1,
        now: datetime | None = None,
    ) -> ProviderRuntimeResponse:
        provider_kind = str(request.provider_kind)
        capability_id = _CAPABILITY_IDS[provider_kind]

        authorization = self._authorize(
            request,
            lease,
            capability_id,
            budget_required=budget_required,
            now=now,
        )
        if authorization.decision == "blocked":
            return blocked_provider_response(
                request,
                authorization.reason,
                redacted_input=authorization.redacted_input,
                fallback_provider_kind=fallback_provider_kind,
            )

        if provider_kind in _EXTERNAL_KINDS and authorization.credential_scope_label is None:
            return blocked_provider_response(
                request,
                "missing_credential_scope",
                fallback_provider_kind=fallback_provider_kind,
            )

        if self._transport_gate is not None and authorization.authority is not None:
            gate = self._transport_gate.evaluate(
                TransportExecutionGateRequest(
                    capability_id=capability_id,
                    transport_kind=TransportKind.provider,
                    credential_scope=authorization.credential_scope_label,
                ),
                authorization.authority,
            )
            if gate.decision == "blocked":
                return blocked_provider_response(
                    request,
                    gate.reason,
                    redacted_input=gate.redacted_input,
                    fallback_provider_kind=fallback_provider_kind,
                )

        adapter = self._adapter_for(provider_kind)
        self._adapter_invocations[provider_kind] = (
            self._adapter_invocations.get(provider_kind, 0) + 1
        )
        response = adapter.generate(request, authorization)
        if response.decision == "blocked" and fallback_provider_kind is not None:
            return response
        return response

    def inspect_untrusted(
        self,
        request: ProviderBoundaryRequest,
        lease: RuntimeLease | None,
        *,
        fallback_provider_kind: str | None = None,
        budget_required: int = 1,
        now: datetime | None = None,
    ) -> ProviderBoundaryResult:
        if request.provider_kind not in _CAPABILITY_IDS:
            return blocked_boundary_result(request, "unsupported_provider")
        for tool_call in request.tool_calls:
            try:
                ProviderToolCall(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    arguments_json=tool_call.arguments_json,
                )
            except ValidationError:
                return blocked_boundary_result(request, "malformed_tool_arguments")
        typed_request = ProviderRuntimeRequest(
            provider_kind=request.provider_kind,
            provider_id=request.provider_id,
            model_id=request.model_id,
            messages=request.messages,
            credential_scope=request.credential_scope,
            network_host=request.network_host,
            live_network=request.live_network,
            metadata=request.metadata,
        )
        provider_kind = str(typed_request.provider_kind)
        constructed_before = provider_kind in self._adapters
        invoked_before = self._adapter_invocations.get(provider_kind, 0)
        response = self.generate(
            typed_request,
            lease,
            fallback_provider_kind=fallback_provider_kind,
            budget_required=budget_required,
            now=now,
        )
        return boundary_result_from_response(
            request=request,
            response=response,
            adapter_invoked=self._adapter_invocations.get(provider_kind, 0) > invoked_before,
            client_constructed=provider_kind in self._adapters and not constructed_before,
        )

    def _adapter_for(self, provider_kind: str) -> ProviderAdapter:
        adapter = self._adapters.get(provider_kind)
        if adapter is not None:
            return adapter
        adapter = self._adapter_factories[provider_kind]()
        self._adapters[provider_kind] = adapter
        return adapter

    def _authorize(
        self,
        request: ProviderRuntimeRequest,
        lease: RuntimeLease | None,
        capability_id: str,
        *,
        budget_required: int,
        now: datetime | None,
    ) -> RuntimeLeaseIntakeResult:
        try:
            intake = RuntimeIntakeRequest(
                runtime_kind="provider",
                capability_id=capability_id,
                credential_scope=request.credential_scope,
                network_host=_network_host_for_intake(request),
                live_network=request.live_network,
                budget_required=budget_required,
                evidence_target=request.evidence_target,
            )
        except ValidationError:
            return RuntimeLeaseIntakeResult(
                decision="blocked",
                reason="malformed_runtime_request",
                runtime_kind="provider",
                capability_id=capability_id,
            )
        return self._lease_builder.authorize(lease, intake, now=now)


def _network_host_for_intake(request: ProviderRuntimeRequest) -> str | None:
    provider_kind = str(request.provider_kind)
    if provider_kind in _EXTERNAL_KINDS:
        return request.network_host
    if request.live_network:
        return request.network_host
    return None
