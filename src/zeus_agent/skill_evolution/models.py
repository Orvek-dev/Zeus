from __future__ import annotations

import hashlib
import json
import re
from typing import Final, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from zeus_agent.security.credentials import redact_secret_like

SkillCandidateStatus = Literal[
    "proposed_not_promoted",
    "review_required",
    "blocked",
    "approved_for_promotion",
]

_SECRET_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_-]*"), "sk-...redacted"),
    (re.compile(r"ghp_[A-Za-z0-9_]+"), "[redacted-secret]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]+"), "[redacted-secret]"),
    (re.compile(r"glpat-[^\s]+"), "[redacted-secret]"),
    (re.compile(r"xox[abp]-[^\s]+"), "[redacted-secret]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"), "[redacted-secret]"),
    (
        re.compile(r"(?i)(api[_-]?key|token|password|secret)=[^\s]+"),
        "[redacted-secret]",
    ),
)

_AUTO_PROMOTION_TERMS: Final[tuple[str, ...]] = (
    "auto promote",
    "auto promotion",
    "auto-promote",
    "automatically promote",
    "self promote",
    "self-promote",
    ".agents/skills",
    "active rules",
    "active skill",
)
_RAW_LOG_TERMS: Final[tuple[str, ...]] = (
    "raw log",
    "raw logs",
    "raw learning log",
    "raw event log",
    "promote logs",
)
_LIVE_TRANSPORT_TERMS: Final[tuple[str, ...]] = (
    "live transport",
    "enable live",
    "live provider",
    "live mcp",
    "live api",
    "live plugin",
)
_AUTHORITY_WIDENING_TERMS: Final[tuple[str, ...]] = (
    "widen authority",
    "expand authority",
    "broaden authority",
    "authority delta",
    "new network grant",
    "network grants",
    "credential grants",
    "capability grants",
)
_EVIDENCE_BYPASS_TERMS: Final[tuple[str, ...]] = (
    "bypass evidence",
    "skip evidence",
    "ignore evidence",
    "disable evidence",
    "bypass gate",
    "bypass gates",
    "skip gate",
    "disable gate",
)


class SkillEvolutionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    title: str
    rationale: str
    source_evidence_ids: list[str]
    status: SkillCandidateStatus = "proposed_not_promoted"
    blocked_reasons: list[str] = Field(default_factory=list)
    authority_delta_allowed: bool = False
    promoted: bool = False

    @field_validator("candidate_id", "title", "rationale")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _redact_sensitive_text(_require_non_empty(value, info.field_name))

    @field_validator("source_evidence_ids", "blocked_reasons")
    @classmethod
    def _validate_text_list(
        cls,
        value: list[str],
        info: ValidationInfo,
    ) -> list[str]:
        if info.field_name == "source_evidence_ids" and not value:
            raise ValueError("source_evidence_ids must be non-empty")
        return [_redact_sensitive_text(_require_non_empty(item, info.field_name)) for item in value]


class SkillPromotionReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    title: str
    rationale: str
    source_evidence_ids: list[str]
    status: SkillCandidateStatus
    blocked_reasons: list[str]
    authority_delta_allowed: bool = False
    promoted: bool = False

    @field_validator("candidate_id", "title", "rationale")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _redact_sensitive_text(_require_non_empty(value, info.field_name))

    @field_validator("source_evidence_ids", "blocked_reasons")
    @classmethod
    def _validate_text_list(cls, value: list[str], info: ValidationInfo) -> list[str]:
        if info.field_name == "source_evidence_ids" and not value:
            raise ValueError("source_evidence_ids must be non-empty")
        return [_redact_sensitive_text(_require_non_empty(item, info.field_name)) for item in value]


def generate_skill_evolution_candidate(
    *,
    evidence_summary: str,
    repeated_failure_tags: Sequence[str] = (),
    improvement_rationale: str | None = None,
    source_evidence_ids: Sequence[str],
) -> SkillEvolutionCandidate:
    summary = _redact_sensitive_text(_require_non_empty(evidence_summary, "evidence_summary"))
    tags = tuple(
        _redact_sensitive_text(_require_non_empty(tag, "repeated_failure_tags"))
        for tag in repeated_failure_tags
    )
    rationale = _redact_sensitive_text(
        _require_non_empty(
            improvement_rationale
            or _default_rationale(summary=summary, repeated_failure_tags=tags),
            "improvement_rationale",
        )
    )
    evidence_ids = [
        _redact_sensitive_text(_require_non_empty(item, "source_evidence_ids"))
        for item in source_evidence_ids
    ]
    candidate_id = _candidate_id(summary, tags, rationale, evidence_ids)
    return SkillEvolutionCandidate(
        candidate_id=candidate_id,
        title=_candidate_title(tags, summary),
        rationale=rationale,
        source_evidence_ids=evidence_ids,
    )


def review_skill_promotion(
    candidate: SkillEvolutionCandidate,
    *,
    explicit_approval: bool,
    requested_authority_delta: bool = False,
) -> SkillPromotionReview:
    blocked_reasons = _dedupe(
        [
            *candidate.blocked_reasons,
            *_unsafe_reasons(candidate, requested_authority_delta),
            *(["explicit_review_required"] if not explicit_approval else []),
        ]
    )
    status = _review_status(blocked_reasons)
    return SkillPromotionReview(
        candidate_id=candidate.candidate_id,
        title=candidate.title,
        rationale=candidate.rationale,
        source_evidence_ids=candidate.source_evidence_ids,
        status=status,
        blocked_reasons=blocked_reasons,
        authority_delta_allowed=False,
        promoted=status == "approved_for_promotion",
    )


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _redact_sensitive_text(value: str) -> str:
    redacted = value
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    if redacted == value and " " not in value:
        return redact_secret_like(value)
    return redacted


def _default_rationale(*, summary: str, repeated_failure_tags: Sequence[str]) -> str:
    if repeated_failure_tags:
        return "Observed repeated failure tags: {0}. Evidence: {1}".format(
            ", ".join(repeated_failure_tags),
            summary,
        )
    return "Observed self-evolution opportunity from evidence: {0}".format(summary)


def _candidate_title(repeated_failure_tags: Sequence[str], summary: str) -> str:
    source = repeated_failure_tags[0] if repeated_failure_tags else summary
    words = re.findall(r"[A-Za-z0-9]+", source)[:4]
    if not words:
        return "Improve Skill Evolution"
    return "Improve {0}".format(" ".join(word.capitalize() for word in words))


def _candidate_id(
    summary: str,
    repeated_failure_tags: Sequence[str],
    rationale: str,
    source_evidence_ids: Sequence[str],
) -> str:
    payload = json.dumps(
        {
            "evidence_summary": summary,
            "repeated_failure_tags": list(repeated_failure_tags),
            "improvement_rationale": rationale,
            "source_evidence_ids": list(source_evidence_ids),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return "skill-candidate-{0}".format(digest)


def _unsafe_reasons(
    candidate: SkillEvolutionCandidate,
    requested_authority_delta: bool,
) -> list[str]:
    text = _review_text(candidate)
    reasons: list[str] = []
    if _contains_any(text, _AUTO_PROMOTION_TERMS):
        reasons.append("auto_promotion_requested")
    if _contains_any(text, _RAW_LOG_TERMS):
        reasons.append("raw_log_promotion_requested")
    if _contains_any(text, _LIVE_TRANSPORT_TERMS):
        reasons.append("live_transport_enablement_requested")
    if requested_authority_delta or _contains_any(text, _AUTHORITY_WIDENING_TERMS):
        reasons.append("authority_widening_requested")
    if _contains_any(text, _EVIDENCE_BYPASS_TERMS):
        reasons.append("evidence_gate_bypass_requested")
    return reasons


def _review_text(candidate: SkillEvolutionCandidate) -> str:
    return " ".join(
        [
            candidate.title,
            candidate.rationale,
            *candidate.source_evidence_ids,
            *candidate.blocked_reasons,
        ]
    ).lower()


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)


def _review_status(blocked_reasons: Sequence[str]) -> SkillCandidateStatus:
    if not blocked_reasons:
        return "approved_for_promotion"
    if blocked_reasons == ["explicit_review_required"]:
        return "review_required"
    return "blocked"


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))
