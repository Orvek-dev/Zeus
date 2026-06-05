from __future__ import annotations

import json
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Final, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import JsonValue

from zeus_agent.live_mcp_external_transport_runtime.response import redact_response

_LOOPBACK_HOSTS: Final = frozenset(("127.0.0.1", "localhost", "::1"))


@dataclass(frozen=True)
class McpCredentialedHttpClientResult:
    status_code: int
    latency_ms: int
    redacted_payload: Optional[dict[str, JsonValue]]


def mcp_endpoint_is_loopback(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    return parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTS


def mcp_endpoint_host(endpoint: str) -> Optional[str]:
    parsed = urlparse(endpoint)
    return parsed.hostname


def post_mcp_body(
    *,
    endpoint: str,
    header_name: str,
    header_value: str,
    body_payload: dict[str, JsonValue],
    timeout_ms: int,
) -> McpCredentialedHttpClientResult:
    body = json.dumps(body_payload).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            header_name: header_value,
        },
        method="POST",
    )
    started = time.monotonic()
    with urlopen(request, timeout=timeout_ms / 1000) as response:
        raw_body = response.read().decode("utf-8")
        status_code = int(response.status)
    latency_ms = int((time.monotonic() - started) * 1000)
    return McpCredentialedHttpClientResult(status_code, latency_ms, _json_object(raw_body))


def _json_object(raw_body: str) -> Optional[dict[str, JsonValue]]:
    try:
        parsed = json.loads(raw_body)
    except JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return redact_response(parsed)
