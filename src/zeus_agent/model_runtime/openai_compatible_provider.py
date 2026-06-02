from __future__ import annotations

from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderToolCall,
    ProviderUsage,
)
from zeus_agent.runtime_lease import RuntimeLeaseIntakeResult


class OpenAICompatibleProviderRuntime:
    def generate(
        self,
        request: ProviderRuntimeRequest,
        authorization: RuntimeLeaseIntakeResult,
    ) -> ProviderRuntimeResponse:
        return ProviderRuntimeResponse(
            decision="dry_run",
            provider_kind=request.provider_kind,
            provider_id=request.provider_id,
            model_id=request.model_id,
            response_id="resp_wave10_openai",
            content="openai-compatible dry run only",
            tool_calls=(
                ProviderToolCall(
                    call_id="call_weather_001",
                    tool_name="get_weather",
                    arguments_json='{"location":"Seoul","days":3}',
                ),
            ),
            usage=ProviderUsage(
                input_tokens=12,
                output_tokens=6,
                budget_units=18,
                latency_ms=0,
            ),
            metadata=(
                ProviderMetadataEntry(
                    key="credential.scope_label",
                    value=authorization.credential_scope_label or "",
                ),
                ProviderMetadataEntry(key="openai.tool_call_style", value="function"),
            ),
        )
