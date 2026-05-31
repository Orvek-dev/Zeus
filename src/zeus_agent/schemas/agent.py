"""Agent loop schemas.

The current Zeus agent loop is intentionally transport-neutral. A future model
transport can decide the next tool calls, while this schema keeps the execution
side auditable and approval-gated today.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


ToolCallStatus = Literal["completed", "blocked", "failed", "skipped"]


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(default_factory=lambda: f"msg_{uuid4().hex}")
    session_id: str
    run_id: str | None = None
    role: Literal["system", "user", "assistant", "tool", "reviewer"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolCallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(default_factory=lambda: f"tool_call_{uuid4().hex}")
    name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    reason: str = ""
    requires_approval: bool = True


class ToolCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    name: str
    status: ToolCallStatus
    summary: str
    result: dict[str, object] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentSessionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(default_factory=lambda: f"agent_report_{uuid4().hex}")
    session_id: str
    run_id: str
    status: Literal["completed", "escalated", "blocked"]
    tool_results: list[ToolCallResult]
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

