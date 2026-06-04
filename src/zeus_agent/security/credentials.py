from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, TypedDict

_SAFE_SCOPE_PATTERN: Final = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_SECRET_LIKE_MARKERS: Final[tuple[str, ...]] = (
    "token=",
    "api-key",
    "api_key",
    "apikey",
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "bearer ",
    "private-key",
    "private_key",
    "private key",
    "secret",
    "password",
    "-----begin",
)
_SECRET_LIKE_PREFIXES: Final[tuple[str, ...]] = (
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
)
_SECRET_SPAN_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9._-]*"), "sk-...redacted"),
    (re.compile(r"ghp_[A-Za-z0-9_]+"), "[redacted-secret]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]+"), "[redacted-secret]"),
    (re.compile(r"glpat-[A-Za-z0-9_-]+"), "[redacted-secret]"),
    (re.compile(r"xox[abp]-[A-Za-z0-9-]+"), "[redacted-secret]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"), "[redacted-secret]"),
    (
        re.compile(
            r"(?is)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        ),
        "[redacted-secret]",
    ),
    (
        re.compile(
            r"(?i)(api[ _-]?key|private[ _-]?key|token|password|secret)\s*[=:]\s*[^\s\"'}]+",
        ),
        "[redacted-secret]",
    ),
    (
        re.compile(
            r"(?i)(aws_access_key_id|aws_secret_access_key|aws_session_token)\s*[=:]\s*[^\s\"'}]+",
        ),
        "[redacted-secret]",
    ),
)


class CredentialReport(TypedDict):
    credential_scopes: list[str]
    count: int


class CredentialScopeUnsafeError(ValueError):
    def __init__(self, payload: dict[str, str]) -> None:
        super().__init__(payload["reason"])
        self.payload = payload


@dataclass(frozen=True)
class CredentialScope:
    label: str

    @classmethod
    def parse(cls, raw_value: str) -> CredentialScope:
        value = raw_value.strip()
        if value == "":
            raise ValueError("credential_scope_empty")
        if _is_secret_like(value):
            redacted = redact_secret_like(value)
            raise CredentialScopeUnsafeError(
                {
                    "reason": "secret_like_credential_scope",
                    "input": redacted,
                    "redacted": redacted,
                },
            )
        if _SAFE_SCOPE_PATTERN.fullmatch(value) is None:
            raise ValueError("credential_scope_invalid")
        return cls(label=value)


def redact_secret_like(raw_value: str) -> str:
    value = raw_value.strip()
    lowered = value.lower()
    if lowered.startswith("sk-"):
        return "sk-...redacted"
    for prefix in _SECRET_LIKE_PREFIXES:
        if lowered.startswith(prefix):
            return "[redacted-secret]"
    for marker in _SECRET_LIKE_MARKERS:
        if marker in lowered:
            return "[redacted-secret]"
    return value


def redact_secret_spans(raw_value: str) -> str:
    value = raw_value.strip()
    redacted = value
    for pattern, replacement in _SECRET_SPAN_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    if redacted != value:
        return redacted
    return redact_secret_like(redacted)


def credential_report(scopes: list[CredentialScope]) -> CredentialReport:
    labels = [scope.label for scope in scopes]
    return CredentialReport(credential_scopes=labels, count=len(labels))


def _is_secret_like(value: str) -> bool:
    redacted = redact_secret_like(value)
    return redacted in {"sk-...redacted", "[redacted-secret]"}
