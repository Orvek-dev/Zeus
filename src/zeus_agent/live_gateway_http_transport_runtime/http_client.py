from __future__ import annotations

import json
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Final, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import JsonValue

from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.security.credentials import redact_secret_spans

_LOOPBACK_HOSTS: Final = frozenset(("127.0.0.1", "localhost", "::1"))


@dataclass(frozen=True)
class GatewayHttpClientResult:
    status_code: int
    latency_ms: int
    redacted_payload: Optional[dict[str, JsonValue]]


def gateway_endpoint_is_loopback(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    return parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTS


def post_gateway(
    gateway_envelope: LiveGatewayDeliveryResult,
    delivery_endpoint: str,
    timeout_ms: int,
) -> GatewayHttpClientResult:
    payload = {
        "adapter_id": gateway_envelope.adapter_id,
        "target": gateway_envelope.target,
        "message_digest": gateway_envelope.message_digest,
        "idempotency_key": gateway_envelope.idempotency_key,
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        delivery_endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with urlopen(request, timeout=timeout_ms / 1000) as response:
        raw_body = response.read().decode("utf-8")
        status_code = int(response.status)
    latency_ms = int((time.monotonic() - started) * 1000)
    return GatewayHttpClientResult(
        status_code=status_code,
        latency_ms=latency_ms,
        redacted_payload=_json_object(raw_body),
    )


def _json_object(raw_body: str) -> Optional[dict[str, JsonValue]]:
    try:
        parsed = json.loads(raw_body)
    except JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return _redact_response(parsed)


def _redact_response(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {redact_secret_spans(key): _redact_value(value) for key, value in payload.items()}


def _redact_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact_secret_spans(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return _redact_response(value)
    return value
