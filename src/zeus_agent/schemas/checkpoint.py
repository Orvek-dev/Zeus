"""Restorable checkpoint schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class SnapshotFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    size: int
    sha256: str
    mode: int
    modified_at: float


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.snapshot_manifest.v1"] = "zeus.snapshot_manifest.v1"
    snapshot_id: str = Field(default_factory=lambda: f"snapshot_{uuid4().hex}")
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    workspace_root: str
    files: list[SnapshotFile] = Field(default_factory=list)
    omitted: list[str] = Field(default_factory=list)
    object_store_root: str


class RestoreReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.restore_report.v1"] = "zeus.restore_report.v1"
    restore_id: str = Field(default_factory=lambda: f"restore_{uuid4().hex}")
    snapshot_id: str
    run_id: str
    restored_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

