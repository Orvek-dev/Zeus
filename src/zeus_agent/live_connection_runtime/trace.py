from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_serializer, field_validator

TraceDecision = Literal[
    "planned",
    "blocked",
    "replay_requested",
    "cleanup_required",
    "cleanup_completed",
]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
)
_REDACTION_TOKEN: Final = "[redacted-secret]"
_SECRET_SPAN_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9._-]*"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"glpat-[A-Za-z0-9_-]+"),
    re.compile(r"xox[abp]-[A-Za-z0-9-]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
        re.DOTALL | re.IGNORECASE,
    ),
    re.compile(
        r"(?i)([\"']?(api[ _-]?key|private[ _-]?key|token|password|secret|"
        r"aws_access_key_id|aws_secret_access_key|aws_session_token)[\"']?\s*[:=]\s*)"
        r"[\"']?[^\"'\s,}]+[\"']?",
    ),
    re.compile(
        r"(?i)(api[ _-]?key|private[ _-]?key|token|password|secret)\s*[=:]\s*[^\s\"'}]+",
    ),
    re.compile(r"(?i)\bprivate[ _-]?key\s*[=:]\s*[^\s\"'}]+"),
)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "api_key=",
    "api-key=",
    "token=",
    "password=",
    "secret=",
    "private_key=",
    "private-key=",
    "private key",
    "begin private key",
    "-----begin",
)


def redact_live_connection_text(value: str) -> str:
    redacted = value.strip()
    for pattern in _SECRET_SPAN_PATTERNS:
        redacted = pattern.sub(_REDACTION_TOKEN, redacted)
    return redacted


def serialized_has_no_secret_echo(value: str) -> bool:
    lowered = value.lower()
    return redact_live_connection_text(value).lower() == lowered and not any(
        marker in lowered
        for marker in _SECRET_MARKERS
    )


class TraceDecisionRecord(BaseModel):
    model_config = _MODEL_CONFIG

    step_id: str
    decision: TraceDecision
    reason: str
    handler_executed: bool = False
    network_opened: bool = False

    @field_validator("step_id", "reason")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, _field_name(info))

    @field_validator("handler_executed", "network_opened")
    @classmethod
    def _reject_side_effect_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_claim_not_allowed")
        return False

    @field_serializer("step_id", "reason")
    def _serialize_text(self, value: str) -> str:
        return redact_live_connection_text(value)


class LiveConnectionTrace(BaseModel):
    model_config = _MODEL_CONFIG

    trace_id: str
    step_ids: tuple[str, ...] = ()
    history: tuple[TraceDecisionRecord, ...] = ()
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True

    @field_validator("trace_id")
    @classmethod
    def _validate_trace_id(cls, value: str) -> str:
        return _require_text(value, "trace_id")

    @field_validator("step_ids")
    @classmethod
    def _validate_step_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_text(value, "step_ids") for value in values)

    @field_validator("handler_executed", "network_opened")
    @classmethod
    def _reject_side_effect_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_claim_not_allowed")
        return False

    @field_serializer("trace_id")
    def _serialize_trace_id(self, value: str) -> str:
        return redact_live_connection_text(value)

    @field_serializer("step_ids")
    def _serialize_step_ids(self, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(redact_live_connection_text(value) for value in values)


def start_live_connection_trace(trace_id: str) -> LiveConnectionTrace:
    return LiveConnectionTrace(trace_id=trace_id)


def append_trace_decision(
    trace: LiveConnectionTrace,
    *,
    step_id: str,
    decision: TraceDecision,
    reason: str,
) -> LiveConnectionTrace:
    record = TraceDecisionRecord(
        step_id=step_id,
        decision=decision,
        reason=reason,
    )
    step_ids = trace.step_ids
    if record.step_id not in step_ids:
        step_ids = (*step_ids, record.step_id)
    return LiveConnectionTrace(
        trace_id=trace.trace_id,
        step_ids=step_ids,
        history=(*trace.history, record),
        handler_executed=False,
        network_opened=False,
        no_secret_echo=True,
    )


def _require_text(value: str, field_name: str) -> str:
    redacted = redact_live_connection_text(value)
    if redacted == "":
        raise ValueError(f"{field_name}_empty")
    return redacted


def _field_name(info: ValidationInfo) -> str:
    if info.field_name is None:
        return "value"
    return info.field_name
