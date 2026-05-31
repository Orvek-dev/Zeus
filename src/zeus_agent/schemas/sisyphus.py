"""Sisyphus goal-runner schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RunStepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    title: str
    status: Literal["completed", "blocked", "skipped", "escalated"]
    evidence_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SisyphusRunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.sisyphus_run_report.v1"] = "zeus.sisyphus_run_report.v1"
    report_id: str = Field(default_factory=lambda: f"sisyphus_{uuid4().hex}")
    run_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["completed", "blocked", "escalated"]
    iterations: int
    progress_score: float
    loop_detected: bool
    step_results: list[RunStepResult]
    escalation_reasons: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)
