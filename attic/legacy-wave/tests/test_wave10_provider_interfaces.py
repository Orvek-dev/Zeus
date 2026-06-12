from __future__ import annotations

import pytest
from pydantic import ValidationError

from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderToolCall,
    ProviderToolResult,
    ProviderUsage,
)


def test_openai_compatible_tool_call_preserves_call_id_and_arguments_json() -> None:
    # Given: an OpenAI-compatible function call with object arguments as JSON.
    arguments_json = '{"location":"Seoul","days":3}'
    call = ProviderToolCall(
        call_id="call_weather_001",
        tool_name="get_weather",
        arguments_json=arguments_json,
    )

    # When: the provider-neutral contract exposes the argument object.
    arguments = call.arguments_as_dict()

    # Then: the call id and original JSON string remain intact.
    assert call.call_id == "call_weather_001"
    assert call.arguments_json == arguments_json
    assert arguments["location"] == "Seoul"
    assert arguments["days"] == 3

    # When / Then: non-object JSON is rejected at the boundary.
    with pytest.raises(ValidationError):
        ProviderToolCall(
            call_id="call_bad_json",
            tool_name="get_weather",
            arguments_json='["not","an","object"]',
        )


def test_anthropic_tool_use_and_tool_result_metadata_are_non_authority() -> None:
    # Given: Anthropic-style tool_use and tool_result metadata.
    response = ProviderRuntimeResponse(
        decision="selected",
        provider_kind="anthropic_metadata",
        provider_id="anthropic-compatible",
        model_id="claude-3-5-sonnet",
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
        usage=ProviderUsage(input_tokens=12, output_tokens=4, budget_units=16, latency_ms=42),
        metadata=(
            ProviderMetadataEntry(key="anthropic.block_type", value="tool_use"),
            ProviderMetadataEntry(key="anthropic.tool_use_id", value="toolu_01weather"),
            ProviderMetadataEntry(key="anthropic.result_block_type", value="tool_result"),
        ),
    )

    # When: metadata is read through the neutral helper.
    block_type = response.metadata_value("anthropic.block_type")
    result_block_type = response.metadata_value("anthropic.result_block_type")

    # Then: Anthropic metadata is preserved without granting authority.
    assert block_type == "tool_use"
    assert result_block_type == "tool_result"
    assert all(entry.is_authority is False for entry in response.metadata)


def test_local_llm_request_carries_endpoint_and_model_metadata() -> None:
    # Given: a local LLM request with endpoint and model metadata.
    request = ProviderRuntimeRequest(
        provider_kind="local_llm",
        provider_id="ollama.local",
        model_id="qwen2.5-coder:7b",
        messages=(ProviderMessage(role="user", content="Summarize the lease."),),
        network_host="127.0.0.1",
        metadata=(
            ProviderMetadataEntry(key="local.endpoint", value="http://127.0.0.1:11434"),
            ProviderMetadataEntry(key="local.runtime_model", value="qwen2.5-coder:7b"),
        ),
    )

    # When: local metadata is read through the neutral helper.
    endpoint = request.metadata_value("local.endpoint")
    runtime_model = request.metadata_value("local.runtime_model")

    # Then: endpoint and model identity stay provider metadata, not raw dict state.
    assert endpoint == "http://127.0.0.1:11434"
    assert runtime_model == "qwen2.5-coder:7b"
    assert request.live_network is False


def test_provider_runtime_response_defaults_block_side_effect_proofs() -> None:
    # Given: a minimal dry-run provider response.
    response = ProviderRuntimeResponse(
        decision="dry_run",
        provider_kind="fake",
        provider_id="fake-local",
        model_id="fake-tool-model",
        response_id="resp_wave10_default",
        content="dry run only",
        usage=ProviderUsage(input_tokens=0, output_tokens=0, budget_units=0, latency_ms=0),
    )

    # When: no side-effect fields are supplied.
    dumped = response.model_dump()

    # Then: defaults prove no handler, network, SDK, credential, or secret echo occurred.
    assert dumped["tool_calls"] == ()
    assert dumped["tool_results"] == ()
    assert response.handler_executed is False
    assert response.network_opened is False
    assert response.sdk_imported is False
    assert response.credential_material_accessed is False
    assert response.no_secret_echo is True
