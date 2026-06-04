from __future__ import annotations

from urllib.error import HTTPError

from pydantic import ValidationError

from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderToolCall,
    ProviderUsage,
)
from zeus_agent.model_runtime.provider_http import (
    LiveHttpConfig,
    http_error_response,
    live_http_config,
    live_http_metadata,
    parse_json_object,
    post_json,
    transport_failure_reason,
)
from zeus_agent.runtime_lease import RuntimeLeaseIntakeResult


class OpenAICompatibleProviderRuntime:
    def generate(
        self,
        request: ProviderRuntimeRequest,
        authorization: RuntimeLeaseIntakeResult,
    ) -> ProviderRuntimeResponse:
        live_config = live_http_config(request, authorization)
        if isinstance(live_config, ProviderRuntimeResponse):
            return live_config
        if isinstance(live_config, LiveHttpConfig):
            return _generate_live_http(request, authorization, live_config)
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


def _generate_live_http(
    request: ProviderRuntimeRequest,
    authorization: RuntimeLeaseIntakeResult,
    config: LiveHttpConfig,
) -> ProviderRuntimeResponse:
    try:
        result = post_json(config, _openai_payload(request))
    except HTTPError as exc:
        return http_error_response(
            request,
            transport_failure_reason(exc),
            config=config,
            network_opened=True,
            status_code=int(exc.code),
        )
    except (OSError, TimeoutError) as exc:
        return http_error_response(
            request,
            transport_failure_reason(exc),
            config=config,
            network_opened=False,
        )
    payload = parse_json_object(result)
    if payload is None:
        return http_error_response(
            request,
            "malformed_http_response",
            config=config,
            network_opened=True,
        )
    parsed = _parse_openai_payload(payload)
    if parsed is None:
        return http_error_response(
            request,
            "malformed_http_response",
            config=config,
            network_opened=True,
        )
    response_id, content, tool_calls, usage = parsed
    metadata = (
        *live_http_metadata(config, authorization, result),
        ProviderMetadataEntry(
            key="credential.scope_label",
            value=authorization.credential_scope_label or "",
        ),
        ProviderMetadataEntry(key="openai.tool_call_style", value="function"),
    )
    return ProviderRuntimeResponse(
        decision="selected",
        provider_kind=request.provider_kind,
        provider_id=request.provider_id,
        model_id=request.model_id,
        response_id=response_id,
        content=content,
        tool_calls=tool_calls,
        usage=usage.model_copy(update={"latency_ms": result.latency_ms}),
        metadata=metadata,
        handler_executed=True,
        network_opened=True,
    )


def _openai_payload(request: ProviderRuntimeRequest) -> dict[str, object]:
    return {
        "model": request.model_id,
        "messages": [
            {"role": message.role, "content": message.content}
            for message in request.messages
        ],
        "stream": request.stream,
    }


def _parse_openai_payload(
    payload: dict[str, object],
) -> tuple[str, str, tuple[ProviderToolCall, ...], ProviderUsage] | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    response_id = payload.get("id")
    usage = _usage(payload.get("usage"))
    if not isinstance(response_id, str) or usage is None:
        return None
    tool_calls = _tool_calls(message.get("tool_calls"))
    if tool_calls is None:
        return None
    return response_id, content, tool_calls, usage


def _tool_calls(value: object) -> tuple[ProviderToolCall, ...] | None:
    if value is None:
        return ()
    if not isinstance(value, list):
        return None
    calls = []
    for entry in value:
        if not isinstance(entry, dict):
            return None
        function = entry.get("function")
        if not isinstance(function, dict):
            return None
        call_id = entry.get("id")
        tool_name = function.get("name")
        arguments = function.get("arguments")
        if not (
            isinstance(call_id, str)
            and isinstance(tool_name, str)
            and isinstance(arguments, str)
        ):
            return None
        try:
            calls.append(
                ProviderToolCall(
                    call_id=call_id,
                    tool_name=tool_name,
                    arguments_json=arguments,
                ),
            )
        except ValidationError:
            return None
    return tuple(calls)


def _usage(value: object) -> ProviderUsage | None:
    if not isinstance(value, dict):
        return None
    prompt_tokens = value.get("prompt_tokens")
    completion_tokens = value.get("completion_tokens")
    total_tokens = value.get("total_tokens")
    if not all(isinstance(item, int) for item in (prompt_tokens, completion_tokens, total_tokens)):
        return None
    return ProviderUsage(
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        budget_units=total_tokens,
        latency_ms=0,
    )
