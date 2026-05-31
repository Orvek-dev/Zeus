"""Best-effort secret redaction for persisted local state.

The goal is not perfect DLP. The goal is to make accidental persistence of
obvious credentials much harder in traces, approvals, and generated specs.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "assignment_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password|passwd|credential)\b"
            r"\s*[:=]\s*([^\s,'\"]{8,})"
        ),
    ),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(A3T|AKIA|ASIA|AGPA|AIDA)[A-Z0-9]{16}\b")),
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
)


@dataclass(frozen=True)
class RedactionResult:
    value: str
    redacted: bool
    findings: tuple[str, ...]


def redact_text(value: str) -> RedactionResult:
    redacted = value
    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(redacted):
            findings.append(label)

            def replacement(match: re.Match[str]) -> str:
                if label == "assignment_secret" and match.lastindex and match.lastindex >= 1:
                    return f"{match.group(1)}=[REDACTED]"
                return "[REDACTED_SECRET]"

            redacted = pattern.sub(replacement, redacted)
    return RedactionResult(
        value=redacted,
        redacted=bool(findings),
        findings=tuple(sorted(set(findings))),
    )


def redact_data(value: Any) -> tuple[Any, bool, tuple[str, ...]]:
    findings: list[str] = []

    def walk(item: Any) -> Any:
        if isinstance(item, str):
            result = redact_text(item)
            findings.extend(result.findings)
            return result.value
        if isinstance(item, list):
            return [walk(child) for child in item]
        if isinstance(item, tuple):
            return tuple(walk(child) for child in item)
        if isinstance(item, dict):
            return {str(key): walk(child) for key, child in item.items()}
        return item

    cleaned = walk(value)
    unique_findings = tuple(sorted(set(findings)))
    return cleaned, bool(unique_findings), unique_findings
