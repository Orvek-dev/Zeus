from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class ConversationLineageEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    turn_id: str
    provider_response_id: str
    tool_call_id: str
    tool_name: str
    tool_decision: str
    evidence_recorded: bool

    @field_validator("session_id", "turn_id", "provider_response_id", "tool_call_id", "tool_name", "tool_decision")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)


class ConversationLineageStore:
    def __init__(self, home: Path) -> None:
        self._home = home
        self._path = home / "wave12-lineage.jsonl"

    def record(self, event: ConversationLineageEvent) -> bool:
        self._home.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as lineage_file:
            lineage_file.write(event.model_dump_json())
            lineage_file.write("\n")
        return self._path.exists() and self._path.stat().st_size > 0
