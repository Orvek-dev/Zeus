from __future__ import annotations

from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderToolCall,
    ProviderToolResult,
    ProviderUsage,
)
from zeus_agent.runtime_lease import RuntimeLeaseIntakeResult


class AnthropicMetadataProviderRuntime:
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
            response_id="msg_01wave10",
            content="",
            tool_calls=(
                ProviderToolCall(
                    call_id="toolu_01weather",
                    tool_name="get_weather",
                    arguments_json='{"location":"Seoul"}',
                ),
            ),
            tool_results=(
                ProviderToolResult(
                    call_id="toolu_01weather",
                    output='{"temperature":"24C"}',
                ),
            ),
            usage=ProviderUsage(
                input_tokens=10,
                output_tokens=4,
                budget_units=14,
                latency_ms=0,
            ),
            metadata=(
                ProviderMetadataEntry(key="anthropic.block_type", value="tool_use"),
                ProviderMetadataEntry(key="anthropic.tool_use_id", value="toolu_01weather"),
                ProviderMetadataEntry(
                    key="anthropic.tool_result_for",
                    value="toolu_01weather",
                ),
                ProviderMetadataEntry(key="anthropic.stop_reason", value="tool_use"),
                ProviderMetadataEntry(
                    key="credential.scope_label",
                    value=authorization.credential_scope_label or "",
                ),
            ),
        )
