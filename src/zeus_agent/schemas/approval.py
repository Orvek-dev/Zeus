"""Human approval records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.approval_record.v1"] = "zeus.approval_record.v1"
    approval_id: str = Field(default_factory=lambda: f"approval_{uuid4().hex}")
    run_id: str
    goal_contract_id: str
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str = "user"
    decision: Literal["approved", "rejected"]
    approval_text: str = ""
    reason: str = ""
    sensitive_input_redacted: bool = False
    redaction_findings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_reason_or_text(self) -> "ApprovalRecord":
        if self.decision == "approved" and not self.approval_text.strip():
            self.approval_text = "Approved by user."
        if self.decision == "rejected" and not self.reason.strip():
            self.reason = "Rejected by user."
        return self
