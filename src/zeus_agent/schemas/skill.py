"""Skill lifecycle schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillState = Literal["draft", "testing", "promoted", "retired"]


class SkillEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    passed: bool
    score: float
    findings: list[str] = Field(default_factory=list)


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.skill_manifest.v1"] = "zeus.skill_manifest.v1"
    skill_id: str
    name: str
    version: str = "0.1.0"
    state: SkillState = "draft"
    description: str
    triggers: list[str] = Field(default_factory=list)
    procedure_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evaluation: SkillEvaluation | None = None
