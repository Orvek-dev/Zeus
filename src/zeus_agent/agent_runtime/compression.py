from __future__ import annotations

from typing import Final, Literal, Sequence

from pydantic import BaseModel, ConfigDict

_INJECTION_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous",
    "developer message",
    "system prompt",
    "reveal secret",
    "exfiltrate",
)


class ContextCompressionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["allowed", "blocked"]
    reason: str
    compressed: bool = False
    message_count: int


class ContextCompressionPolicy:
    def __init__(self, *, threshold: int = 4) -> None:
        self._threshold = threshold

    def evaluate(self, messages: Sequence[str]) -> ContextCompressionResult:
        if any(_has_injection_marker(message) for message in messages):
            return ContextCompressionResult(
                decision="blocked",
                reason="unsafe_context_injection",
                message_count=len(messages),
            )
        return ContextCompressionResult(
            decision="allowed",
            reason="context_allowed",
            compressed=len(messages) > self._threshold,
            message_count=len(messages),
        )


def _has_injection_marker(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _INJECTION_MARKERS)
