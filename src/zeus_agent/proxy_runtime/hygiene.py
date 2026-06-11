"""Proxy log-hygiene policy modes (P12).

`count` is the alpha-honest default — the proxy scans response bodies for
secret-shaped material and counts findings, but returns the body unchanged.
The other modes give the secret-leak surface real teeth:

- `redact` strips secret spans from the text the host receives (and, for
  streaming, holds a rolling tail so a key split across SSE deltas is
  reassembled before any chunk is released).
- `block` withholds the whole response.
- `ask` parks the response for operator review and withholds it until approved.

A mode that MUTATES or WITHHOLDS the body is itself recorded as a decision
receipt (P11 invariant: the final action the host sees always has a receipt).
"""

from __future__ import annotations

import copy
from enum import Enum
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

KV_HYGIENE_MODE: Final = "hygiene.mode"
# Secrets can straddle SSE chunk boundaries; hold this many trailing characters
# back until the next delta so a split key is reassembled before redaction. A
# secret longer than this window is the documented blind spot.
STREAM_TAIL_WINDOW: Final = 256


class HygieneMode(str, Enum):
    count = "count"
    redact = "redact"
    block = "block"
    ask = "ask"

    @classmethod
    def parse(cls, raw: Optional[str]) -> "HygieneMode":
        if raw is None:
            return cls.count
        try:
            return cls(raw.strip().lower())
        except ValueError:
            return cls.count


def hygiene_mode_of(store: Optional[SQLiteControlPlaneStore]) -> HygieneMode:
    if store is None:
        return HygieneMode.count
    return HygieneMode.parse(store.kv_get(KV_HYGIENE_MODE))


def redact_chat_body(body: dict[str, JsonValue]) -> tuple[dict[str, JsonValue], int]:
    """Redact secret spans in assistant message content. Returns (body, count)."""
    out = copy.deepcopy(body)
    count = 0
    choices = out.get("choices")
    for choice in choices if isinstance(choices, list) else []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content:
            redacted = redact_secret_spans(content)
            if redacted != content:
                message["content"] = redacted
                count += 1
    return out, count


def redact_responses_body(body: dict[str, JsonValue]) -> tuple[dict[str, JsonValue], int]:
    """Redact secret spans in /v1/responses output_text items."""
    out = copy.deepcopy(body)
    count = 0
    output = out.get("output")
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                redacted = redact_secret_spans(text)
                if redacted != text:
                    part["text"] = redacted
                    count += 1
    return out, count


class RollingRedactor:
    """Per-choice rolling window so a secret split across SSE deltas is
    reassembled and redacted before any chunk reaches the host."""

    def __init__(self, window: int = STREAM_TAIL_WINDOW) -> None:
        self._tails: dict[int, str] = {}
        self._window = window
        self.redactions = 0

    def feed(self, choice_index: int, text: str) -> str:
        """Append `text` to this choice's buffer; return the redacted prefix
        that is safe to release now (the trailing window is held back)."""
        buffer = self._tails.get(choice_index, "") + text
        redacted = redact_secret_spans(buffer)
        if redacted != buffer:
            self.redactions += 1
            buffer = redacted
        if len(buffer) <= self._window:
            self._tails[choice_index] = buffer
            return ""
        cut = len(buffer) - self._window
        self._tails[choice_index] = buffer[cut:]
        return buffer[:cut]

    def flush(self, choice_index: int) -> str:
        """Release the held tail for a finished choice, redacted."""
        tail = self._tails.pop(choice_index, "")
        if not tail:
            return ""
        redacted = redact_secret_spans(tail)
        if redacted != tail:
            self.redactions += 1
        return redacted
