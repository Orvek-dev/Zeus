from __future__ import annotations

import json
from typing import Final

from pydantic import JsonValue

from zeus_agent.security.credentials import redact_secret_spans

SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


def redact_response(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    redacted = {}
    for key, value in payload.items():
        redacted[redact_secret_spans(key)] = redact_value(value)
    return redacted


def redact_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact_secret_spans(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {redact_secret_spans(key): redact_value(item) for key, item in value.items()}
    return value


def no_secret_echo(payload: dict[str, JsonValue]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    return not any(marker in serialized for marker in SECRET_MARKERS)
