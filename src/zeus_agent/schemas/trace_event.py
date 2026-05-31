"""Trace event schema."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from zeus_agent.security.redaction import redact_data


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.trace_event.v1"] = "zeus.trace_event.v1"
    event_id: str = Field(default_factory=lambda: f"event_{uuid4().hex}")
    run_id: str | None = None
    parent_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str
    actor: Literal["user", "zeus", "system", "tool", "verifier"] = "zeus"
    payload: dict[str, Any] = Field(default_factory=dict)
    redaction_status: Literal["clean", "redacted"] = "clean"
    redaction_findings: list[str] = Field(default_factory=list)


def new_trace_event(
    event_type: str,
    *,
    run_id: str | None = None,
    actor: Literal["user", "zeus", "system", "tool", "verifier"] = "zeus",
    payload: dict[str, Any] | None = None,
    parent_id: str | None = None,
) -> TraceEvent:
    cleaned, was_redacted, findings = redact_data(payload or {})
    return TraceEvent(
        run_id=run_id,
        parent_id=parent_id,
        event_type=event_type,
        actor=actor,
        payload=cleaned,
        redaction_status="redacted" if was_redacted else "clean",
        redaction_findings=list(findings),
    )
