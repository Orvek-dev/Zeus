from __future__ import annotations

from typing import Final

# Deterministic prompt-injection tells. The list is intentionally small and
# auditable — the scanner's job is to taint and re-quarantine, not to be an
# oracle; anything it misses is still bounded by capability decisions.
_INJECTION_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard your instructions",
    "disregard all previous",
    "you are now",
    "new system prompt",
    "system prompt:",
    "begin system",
    "do not tell the user",
    "without telling the user",
    "exfiltrate",
    "send your credentials",
)
_ZERO_WIDTH: Final[tuple[str, ...]] = ("​", "‌", "‍", "﻿", "⁠")


def scan_for_injection(text: str) -> tuple[str, ...]:
    """Return the matched injection tells (empty tuple = clean)."""
    if not text:
        return ()
    findings: list[str] = []
    lowered = text.lower()
    for marker in _INJECTION_MARKERS:
        if marker in lowered:
            findings.append("marker:{0}".format(marker))
    for char in _ZERO_WIDTH:
        if char in text:
            findings.append("zero_width:U+{0:04X}".format(ord(char)))
            break
    return tuple(findings)
