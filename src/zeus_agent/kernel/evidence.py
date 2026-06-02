from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text


class MnemeEvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    goal_contract_id: str
    criterion_id: str
    evidence_type: str
    summary: str
    status: EvidenceStatus
    capability_id: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)

    @field_validator(
        "run_id",
        "goal_contract_id",
        "criterion_id",
        "evidence_type",
        "summary",
    )
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("capability_id")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "capability_id")

    @field_validator("artifacts")
    @classmethod
    def _validate_artifacts(cls, values: List[str]) -> List[str]:
        return [_require_non_empty(value, "artifacts") for value in values]
