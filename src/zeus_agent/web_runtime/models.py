from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationInfo, field_validator, model_validator

from zeus_agent.security.credentials import redact_secret_spans

WebDecision = Literal["planned", "blocked"]
WebFreshnessState = Literal["fresh", "stale"]
WebSecretField = Literal["source_id", "source_url", "source_ref", "summary"]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    strict=True,
)


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


class WebSourcePin(BaseModel):
    model_config = _MODEL_CONFIG

    source_id: str
    source_url: str
    source_ref: Optional[str]
    source_pinned: bool = True
    freshness: WebFreshnessState = "fresh"
    summary: str
    secret_fields: tuple[WebSecretField, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _redact_and_mark_secrets(cls, data: JsonValue) -> JsonValue:
        if not isinstance(data, dict):
            return data
        secret_fields: list[WebSecretField] = []
        safe = dict(data)
        for field_name in ("source_id", "source_url", "source_ref", "summary"):
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

    @field_validator("source_id", "source_url", "summary")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _safe_text(value, info.field_name)

    @field_validator("source_ref")
    @classmethod
    def _validate_source_ref(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _safe_text(value, "source_ref")

    @field_validator("freshness", mode="before")
    @classmethod
    def _validate_freshness(cls, value: JsonValue) -> JsonValue:
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("freshness must be non-empty")
        return value

    @field_validator("secret_fields", mode="before")
    @classmethod
    def _coerce_secret_fields(
        cls,
        value: JsonValue,
    ) -> JsonValue | tuple[JsonValue, ...]:
        return _coerce_tuple(value)


class WebResearchDispatch(BaseModel):
    model_config = _MODEL_CONFIG

    source_id: str
    source_ref: Optional[str]
    handler_executed: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False


class WebResearchEvidence(BaseModel):
    model_config = _MODEL_CONFIG

    surface_kind: Literal["web"] = "web"
    source_id: str
    source_url: str
    source_ref: Optional[str]
    source_pinned: bool
    freshness: WebFreshnessState
    summary: str
    secret_fields: tuple[WebSecretField, ...]
    no_secret_echo: bool = True


class WebResearchEnvelope(BaseModel):
    model_config = _MODEL_CONFIG

    decision: WebDecision
    reason: str
    dispatch: WebResearchDispatch
    evidence: WebResearchEvidence
    handler_executed: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False
    no_secret_echo: bool = True


__all__ = [
    "WebDecision",
    "WebFreshnessState",
    "WebResearchDispatch",
    "WebResearchEnvelope",
    "WebResearchEvidence",
    "WebSecretField",
    "WebSourcePin",
]
