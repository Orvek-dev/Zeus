from __future__ import annotations

import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_STRICT_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
)
ParallelScheduleDecision = Literal["blocked", "planned"]
ParallelSecurityDecision = Literal["allow_live_network"]


class ParallelTaskSpec(BaseModel):
    model_config = _STRICT_CONFIG

    task_id: str
    owned_paths: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    security_decisions: tuple[ParallelSecurityDecision, ...] = ()
    evidence_target: Optional[str] = None
    manual_qa_channel: str = "script-pty"
    subagent_depth: int = 1
    live_capable: bool = False

    @field_validator("task_id")
    @classmethod
    def _validate_scoped_text(cls, value: str, info: ValidationInfo) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("{0}_empty".format(info.field_name))
        if not _ID_PATTERN.fullmatch(normalized):
            raise ValueError("malformed_{0}".format(info.field_name))
        return normalized

    @field_validator("manual_qa_channel")
    @classmethod
    def _validate_manual_qa_channel(cls, value: str) -> str:
        return _validate_scope(value, "manual_qa_channel")

    @field_validator("owned_paths")
    @classmethod
    def _validate_owned_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("owned_paths_empty")
        deduped = _dedupe(values)
        return tuple(_validate_scope(path, "owned_paths") for path in deduped)

    @field_validator("depends_on")
    @classmethod
    def _validate_depends_on(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = _dedupe(values)
        for dependency in normalized:
            if not _ID_PATTERN.fullmatch(dependency):
                raise ValueError("malformed_depends_on")
        return tuple(normalized)

    @field_validator("security_decisions")
    @classmethod
    def _validate_security_decisions(cls, values: tuple[ParallelSecurityDecision, ...]) -> tuple[ParallelSecurityDecision, ...]:
        return tuple(_dedupe(values))

    @field_validator("evidence_target")
    @classmethod
    def _normalize_evidence_target(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @field_validator("subagent_depth")
    @classmethod
    def _validate_subagent_depth(cls, value: int) -> int:
        if value < 1:
            raise ValueError("subagent_depth_must_be_positive")
        return value


class ParallelWavePlan(BaseModel):
    model_config = _STRICT_CONFIG

    wave_index: int
    task_ids: tuple[str, ...]
    manual_qa_channels: tuple[str, ...]

    @field_validator("wave_index")
    @classmethod
    def _validate_wave_index(cls, value: int) -> int:
        if value < 0:
            raise ValueError("wave_index_must_be_non_negative")
        return value

    @field_validator("task_ids")
    @classmethod
    def _validate_task_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("wave_task_ids_empty")
        return tuple(values)


class ParallelSchedule(BaseModel):
    model_config = _STRICT_CONFIG

    decision: ParallelScheduleDecision
    reason: str
    waves: tuple[ParallelWavePlan, ...]
    blocked_reasons: tuple[str, ...]
    handler_executed: bool = False
    network_opened: bool = False
    dry_run: bool = True


def _dedupe(values: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            raise ValueError("sequence_entry_empty")
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _validate_scope(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0}_empty".format(field_name))
    return normalized
