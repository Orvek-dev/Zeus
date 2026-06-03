from __future__ import annotations

import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationInfo, field_validator, model_validator

from zeus_agent.security.credentials import redact_secret_spans

GitHubDecision = Literal["planned", "blocked"]
GitHubSecretField = Literal[
    "repo",
    "ref",
    "query",
    "query_evidence_id",
    "summary",
]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    strict=True,
)
_REPO_PATTERN: Final = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _contains_secret_like(value: str) -> bool:
    normalized = value.strip()
    return redact_secret_spans(normalized) != normalized


def _safe_text(value: str, field_name: str) -> str:
    return redact_secret_spans(_require_non_empty(value, field_name))


def _coerce_tuple(value: JsonValue) -> JsonValue | tuple[JsonValue, ...]:
    if isinstance(value, list):
        return tuple(value)
    return value


class GitHubSourcePin(BaseModel):
    model_config = _MODEL_CONFIG

    repo: str
    ref: Optional[str]
    query: str
    query_evidence_id: Optional[str]
    source_pinned: bool = True
    summary: str
    secret_fields: tuple[GitHubSecretField, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _redact_and_mark_secrets(cls, data: JsonValue) -> JsonValue:
        if not isinstance(data, dict):
            return data
        secret_fields: list[GitHubSecretField] = []
        safe = dict(data)
        for field_name in ("repo", "ref", "query", "query_evidence_id", "summary"):
            raw_value = data.get(field_name)
            if raw_value is None:
                continue
            if not isinstance(raw_value, str):
                continue
            if _contains_secret_like(raw_value):
                secret_fields.append(field_name)
            safe[field_name] = redact_secret_spans(raw_value.strip())
        safe["secret_fields"] = tuple(secret_fields)
        return safe

    @field_validator("repo")
    @classmethod
    def _validate_repo(cls, value: str) -> str:
        normalized = _safe_text(value, "repo")
        if _REPO_PATTERN.fullmatch(normalized) is None:
            raise ValueError("github_repo_must_be_owner_repo")
        return normalized

    @field_validator("query", "summary")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _safe_text(value, info.field_name)

    @field_validator("ref", "query_evidence_id")
    @classmethod
    def _validate_optional_text(
        cls,
        value: Optional[str],
        info: ValidationInfo,
    ) -> Optional[str]:
        if value is None:
            return None
        return _safe_text(value, info.field_name)

    @field_validator("secret_fields", mode="before")
    @classmethod
    def _coerce_secret_fields(
        cls,
        value: JsonValue,
    ) -> JsonValue | tuple[JsonValue, ...]:
        return _coerce_tuple(value)


class GitHubResearchDispatch(BaseModel):
    model_config = _MODEL_CONFIG

    repo: str
    ref: Optional[str]
    query_evidence_id: Optional[str]
    handler_executed: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False


class GitHubResearchEvidence(BaseModel):
    model_config = _MODEL_CONFIG

    surface_kind: Literal["github"] = "github"
    repo: str
    ref: Optional[str]
    query: str
    query_evidence_id: Optional[str]
    source_pinned: bool
    summary: str
    secret_fields: tuple[GitHubSecretField, ...]
    no_secret_echo: bool = True


class GitHubResearchEnvelope(BaseModel):
    model_config = _MODEL_CONFIG

    decision: GitHubDecision
    reason: str
    dispatch: GitHubResearchDispatch
    evidence: GitHubResearchEvidence
    handler_executed: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False
    no_secret_echo: bool = True


__all__ = [
    "GitHubDecision",
    "GitHubResearchDispatch",
    "GitHubResearchEnvelope",
    "GitHubResearchEvidence",
    "GitHubSecretField",
    "GitHubSourcePin",
]
