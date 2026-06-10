from __future__ import annotations

import re
from typing import Final

# Prompt-injection markers in an MCP tool *description* — the description is
# untrusted text from a third-party server and is a known attack vector.
_INJECTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"ignore\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(prompt|instructions|system)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now", re.IGNORECASE),
    re.compile(r"override\s+(your|the)\s+(rules|instructions|policy)", re.IGNORECASE),
    re.compile(r"exfiltrat", re.IGNORECASE),
    re.compile(r"send\s+(the\s+)?(credentials|secrets|api\s*key|token)", re.IGNORECASE),
    re.compile(r"base64", re.IGNORECASE),
    re.compile(r"do\s+not\s+(tell|inform|mention)", re.IGNORECASE),
)


def scan_tool_description(text: str) -> tuple[str, ...]:
    """Return the injection markers found in a tool description (empty = clean)."""
    found: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            found.append(match.re.pattern)
    return tuple(found)
