from __future__ import annotations

import json
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import JsonValue

from zeus_agent.security.credentials import redact_secret_spans

_ERROR_PAYLOAD_KEY: Final = "error"


@dataclass(frozen=True)
class ResearchJsonFetchResult:
    status_code: int
    latency_ms: int
    payload: dict[str, JsonValue]


def get_research_json(*, url: str, timeout_ms: int) -> ResearchJsonFetchResult:
    started = time.monotonic()
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout_ms / 1000) as response:
            raw_body = response.read().decode("utf-8")
            status_code = int(response.status)
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8")
        status_code = int(exc.code)
    except (OSError, URLError) as exc:
        return ResearchJsonFetchResult(
            status_code=0,
            latency_ms=_latency(started),
            payload={_ERROR_PAYLOAD_KEY: redact_secret_spans(str(exc))},
        )
    return ResearchJsonFetchResult(
        status_code=status_code,
        latency_ms=_latency(started),
        payload=_json_payload(raw_body),
    )


def _latency(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _json_payload(raw_body: str) -> dict[str, JsonValue]:
    try:
        parsed = json.loads(raw_body)
    except JSONDecodeError:
        return {_ERROR_PAYLOAD_KEY: "research_response_not_json_object"}
    if not isinstance(parsed, dict):
        return {_ERROR_PAYLOAD_KEY: "research_response_not_json_object"}
    return _redact_object(parsed)


def _redact_object(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {redact_secret_spans(str(key)): _redact_value(value) for key, value in payload.items()}


def _redact_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact_secret_spans(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return _redact_object(value)
    return value
