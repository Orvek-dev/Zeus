"""Mneme evidence schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.evidence_record.v1"] = "zeus.evidence_record.v1"
    evidence_id: str = Field(default_factory=lambda: f"evidence_{uuid4().hex}")
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_type: Literal["checkpoint", "command", "diff", "verification", "skill", "note"]
    summary: str
    artifact_paths: list[str] = Field(default_factory=list)
    passed: bool | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    redaction_status: Literal["clean", "redacted"] = "clean"
    redaction_findings: list[str] = Field(default_factory=list)


class DiffGateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.diff_gate_report.v1"] = "zeus.diff_gate_report.v1"
    report_id: str = Field(default_factory=lambda: f"diff_gate_{uuid4().hex}")
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    workspace_root: str
    is_git_repo: bool
    changed_files: list[str] = Field(default_factory=list)
    forbidden_path_hits: list[str] = Field(default_factory=list)
    allowed: bool
    requires_human_review: bool
    summary: str
    artifact_path: str | None = None
