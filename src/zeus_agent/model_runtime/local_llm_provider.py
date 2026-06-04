from __future__ import annotations

from typing import Final
from urllib.error import HTTPError

from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
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

_DEFAULT_ENDPOINT: Final = "http://127.0.0.1:11434"


class LocalLLMProviderRuntime:
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


def _generate_live_http(
    request: ProviderRuntimeRequest,
    authorization: RuntimeLeaseIntakeResult,
    config: LiveHttpConfig,
) -> ProviderRuntimeResponse:
    try:
        result = post_json(config, _local_payload(request))
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
    response = payload.get("response")
    if not isinstance(response, str):
        return http_error_response(
            request,
            "malformed_http_response",
            config=config,
            network_opened=True,
        )
    prompt_tokens = _int_value(payload.get("prompt_eval_count"))
    output_tokens = _int_value(payload.get("eval_count"))
    runtime_model = request.metadata_value("local.runtime_model") or request.model_id
    metadata = (
        *live_http_metadata(config, authorization, result),
        ProviderMetadataEntry(key="local.endpoint", value=config.endpoint),
        ProviderMetadataEntry(key="local.runtime_model", value=str(runtime_model)),
        ProviderMetadataEntry(key="capability.id", value=authorization.capability_id),
    )
    return ProviderRuntimeResponse(
        decision="selected",
        provider_kind=request.provider_kind,
        provider_id=request.provider_id,
        model_id=request.model_id,
        response_id="resp_wave16_local_http",
        content=response,
        usage=ProviderUsage(
            input_tokens=prompt_tokens,
            output_tokens=output_tokens,
            budget_units=prompt_tokens + output_tokens,
            latency_ms=result.latency_ms,
        ),
        metadata=metadata,
        handler_executed=True,
        network_opened=True,
    )


def _local_payload(request: ProviderRuntimeRequest) -> dict[str, object]:
    prompt = "\n".join(message.content for message in request.messages)
    return {"model": request.model_id, "prompt": prompt, "stream": False}


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0
