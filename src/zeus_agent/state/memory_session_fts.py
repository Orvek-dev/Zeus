from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from zeus_agent.security.credentials import redact_secret_like

_SECRET_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_-]*"), "sk-...redacted"),
    (re.compile(r"ghp_[A-Za-z0-9_]+"), "[redacted-secret]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]+"), "[redacted-secret]"),
    (re.compile(r"(?i)(api[_-]?key|token|password|secret)=[^\s]+"), "[redacted-secret]"),
)


@dataclass(frozen=True)
class MemorySessionDocument:
    session_id: str
    principal_id: str
    raw_text: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class MemorySessionFTSRecord:
    session_id: str
    principal_id: str
    redacted_text: str
    terms: tuple[str, ...]


class MemorySessionFTSIndex:
    def __init__(self) -> None:
        self._records: list[MemorySessionFTSRecord] = []

    def add(self, document: MemorySessionDocument) -> MemorySessionFTSRecord:
        record = MemorySessionFTSRecord(
            session_id=redact_secret_like(document.session_id),
            principal_id=redact_secret_like(document.principal_id),
            redacted_text=redact_memory_text(document.raw_text),
            terms=_terms(document),
        )
        self._records.append(record)
        return record

    def search(self, query: str) -> tuple[MemorySessionFTSRecord, ...]:
        normalized = query.casefold()
        return tuple(
            record
            for record in self._records
            if normalized in record.redacted_text.casefold() or normalized in record.terms
        )

    def records(self) -> tuple[MemorySessionFTSRecord, ...]:
        return tuple(self._records)


def redact_memory_text(raw_text: str) -> str:
    redacted = raw_text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redact_secret_like(redacted)


def raw_secret_present(
    records: tuple[MemorySessionFTSRecord, ...],
    raw_secret: str,
) -> bool:
    return any(raw_secret in record.redacted_text for record in records)


def _terms(document: MemorySessionDocument) -> tuple[str, ...]:
    searchable = " ".join((document.raw_text, *document.tags))
    return tuple(
        sorted(
            {
                token.casefold()
                for token in re.findall(r"[A-Za-z0-9_.-]+", redact_memory_text(searchable))
            },
        ),
    )
