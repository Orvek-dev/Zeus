from __future__ import annotations

import re
from typing import Final

from pydantic import ValidationError

from zeus_agent.objective_runtime import ObjectiveCompiler

_UNSAFE_POLICY_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (
        re.compile(
            r"\b(?:execute|invoke|run|call|trigger)\s+(?:all\s+)?"
            r"(?:handlers?|tool\s+handlers?|runtime\s+handlers?)\b",
            re.IGNORECASE,
        ),
        "handler_execution_requested",
    ),
    (
        re.compile(
            r"\b(?:open|enable|grant|allow)\s+(?:unrestricted\s+|all\s+)?"
            r"(?:internet|network|egress|live\s+network|outbound\s+connectivity)(?:\s+access)?\b|"
            r"\bestablish\s+outbound\s+connectivity\b",
            re.IGNORECASE,
        ),
        "live_transport_enablement_requested",
    ),
    (
        re.compile(
            r"\b(?:connect|call|use|enable|activate|perform|hit|query|request)\s+"
            r"(?:to\s+|against\s+)?(?:the\s+|a\s+)?"
            r"(?:external|production|real|live|paid)\s+(?:ai\s+|openai\s+)?"
            r"(?:provider|api|endpoint|model|provider\s+transport|model\s+endpoint|request)\b|"
            r"\bmake\s+(?:a\s+)?(?:external|production|real|live|paid)\s+"
            r"(?:openai\s+)?request\b|"
            r"\bprovider\s+transport\s+against\s+the\s+paid\b|"
            r"\breal\s+model\s+endpoint\b",
            re.IGNORECASE,
        ),
        "live_production_claim_requested",
    ),
    (
        re.compile(
            r"\b(?:write|install|create|promote|modify|edit|persist)\s+"
            r"(?:new\s+|repo\s+|runtime\s+|active\s+|\.codex\s+)?"
            r"(?:polic(?:y|ies)|rules?|skills?)\b|\.agents/skills|\.codex",
            re.IGNORECASE,
        ),
        "active_policy_write_requested",
    ),
    (
        re.compile(
            r"\b(?:auto-promote|auto\s+promotion|automatic\s+promotion|"
            r"self-promote|promote\s+\w+\s+without\s+review)\b",
            re.IGNORECASE,
        ),
        "auto_promotion_requested",
    ),
    (
        re.compile(r"\bexternal\s+delivery\b", re.IGNORECASE),
        "external_delivery_requested",
    ),
    (
        re.compile(
            r"\b(?:ship|deploy|release|send)\s+(?:it\s+)?to\s+production\b|"
            r"\blive\s+production\s+claim\b",
            re.IGNORECASE,
        ),
        "live_production_claim_requested",
    ),
)


def unsafe_policy_reasons(text: str) -> tuple[str, ...]:
    reasons: list[str] = []
    try:
        compiled = ObjectiveCompiler().compile(text)
    except ValidationError:
        return ("malformed_policy_text",)
    if compiled.blocked:
        reasons.extend(compiled.block_reasons)
    lowered = text.lower()
    for pattern, reason in _UNSAFE_POLICY_PATTERNS:
        if pattern.search(lowered) is not None:
            reasons.append(reason)
    return tuple(dict.fromkeys(reasons))
