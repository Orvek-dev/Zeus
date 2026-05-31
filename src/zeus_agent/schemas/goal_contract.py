"""Goal contract schema.

The goal contract is the first ground-truth oracle in Zeus. It converts intent
into a finite, reviewable agreement before any execution begins.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ApprovalState = Literal["draft", "pending_approval", "approved", "rejected", "superseded"]
GoalMode = Literal["conversation", "blueprint", "execution"]
RiskLevel = Literal["low", "medium", "high"]


class GoalContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.goal_contract.v1"] = "zeus.goal_contract.v1"
    goal_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_user_request: str
    normalized_goal: str
    mode: GoalMode = "blueprint"
    deliverables: list[str]
    acceptance_criteria: list[str]
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "medium"
    requires_human_approval: bool = True
    approval_state: ApprovalState = "pending_approval"
    forbidden_actions: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    sensitive_input_redacted: bool = False
    redaction_findings: list[str] = Field(default_factory=list)

    @field_validator("raw_user_request", "normalized_goal")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        return cleaned

    @field_validator("deliverables", "acceptance_criteria")
    @classmethod
    def non_empty_list(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("list must not be empty")
        return cleaned
