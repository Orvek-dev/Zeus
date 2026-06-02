from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecutionMode(str, Enum):
    PLAN_ONLY = "plan_only"
    AUTHORIZED_DISPATCH = "authorized_dispatch"


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text


class GoalContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_contract_id: str
    raw_user_request: str
    normalized_goal: str
    deliverables: List[str] = Field(min_length=1)
    acceptance_criteria: List[str] = Field(min_length=1)

    @field_validator("goal_contract_id", "raw_user_request", "normalized_goal")
    @classmethod
    def _validate_text_fields(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("deliverables", "acceptance_criteria")
    @classmethod
    def _validate_non_empty_lists(cls, values: List[str], info: object) -> List[str]:
        cleaned = [_require_non_empty(value, info.field_name) for value in values]
        if not cleaned:
            raise ValueError("{0} must be non-empty".format(info.field_name))
        return cleaned


class ExecutionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    goal_contract_id: str
    execution_mode: ExecutionMode = ExecutionMode.PLAN_ONLY

    @field_validator("run_id", "goal_contract_id")
    @classmethod
    def _validate_ids(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)
