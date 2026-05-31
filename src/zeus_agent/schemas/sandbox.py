"""Sandbox runtime schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class FileFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    size: int
    sha256: str
    modified_at: float


class SandboxCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.sandbox_checkpoint.v1"] = "zeus.sandbox_checkpoint.v1"
    checkpoint_id: str = Field(default_factory=lambda: f"checkpoint_{uuid4().hex}")
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    workspace_root: str
    file_count: int
    total_bytes: int
    files: list[FileFingerprint]
    omitted: list[str] = Field(default_factory=list)
    content_snapshot_path: str | None = None
    restorable: bool = False


class SandboxCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.sandbox_command.v1"] = "zeus.sandbox_command.v1"
    command_id: str = Field(default_factory=lambda: f"command_{uuid4().hex}")
    run_id: str
    argv: list[str]
    cwd: str
    timeout_seconds: int
    network_policy: Literal["deny_by_default", "allowlist", "open"]
    approved: bool


class SandboxResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.sandbox_result.v1"] = "zeus.sandbox_result.v1"
    result_id: str = Field(default_factory=lambda: f"result_{uuid4().hex}")
    command_id: str
    run_id: str
    started_at: datetime
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    argv: list[str]
    cwd: str
    exit_code: int | None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    redaction_status: Literal["clean", "redacted"] = "clean"
    redaction_findings: list[str] = Field(default_factory=list)
    artifact_path: str | None = None
    stdout_artifact_path: str | None = None
    stderr_artifact_path: str | None = None
    stdout_truncated: bool = False
    stderr_truncated: bool = False
