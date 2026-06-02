from __future__ import annotations

from typing import Final

from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderUsage,
)
from zeus_agent.runtime_lease import RuntimeLeaseIntakeResult

_DEFAULT_ENDPOINT: Final = "http://127.0.0.1:11434"


class LocalLLMProviderRuntime:
    def generate(
        self,
        request: ProviderRuntimeRequest,
        authorization: RuntimeLeaseIntakeResult,
    ) -> ProviderRuntimeResponse:
        endpoint = request.metadata_value("local.endpoint") or _DEFAULT_ENDPOINT
        runtime_model = request.metadata_value("local.runtime_model") or request.model_id
        return ProviderRuntimeResponse(
            decision="selected",
            provider_kind=request.provider_kind,
            provider_id=request.provider_id,
            model_id=request.model_id,
            response_id="resp_wave10_local",
            content="local LLM dry-run response",
            usage=ProviderUsage(
                input_tokens=0,
                output_tokens=4,
                budget_units=1,
                latency_ms=0,
            ),
            metadata=(
                ProviderMetadataEntry(key="local.endpoint", value=endpoint),
                ProviderMetadataEntry(key="local.runtime_model", value=runtime_model),
                ProviderMetadataEntry(key="capability.id", value=authorization.capability_id),
            ),
        )
