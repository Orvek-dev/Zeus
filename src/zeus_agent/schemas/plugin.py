"""Plugin, MCP, cron, and gateway registry schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.plugin_manifest.v1"] = "zeus.plugin_manifest.v1"
    plugin_id: str = Field(default_factory=lambda: f"plugin_{uuid4().hex}")
    name: str
    kind: Literal["local_plugin", "mcp_server", "tool_pack"]
    description: str = ""
    entrypoint: str = ""
    enabled: bool = False
    risk_level: Literal["low", "medium", "high"] = "medium"
    requires_approval: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CronJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.cron_job.v1"] = "zeus.cron_job.v1"
    job_id: str = Field(default_factory=lambda: f"cron_{uuid4().hex}")
    name: str
    schedule: str
    command: list[str]
    enabled: bool = False
    requires_approval: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GatewayAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.gateway_adapter.v1"] = "zeus.gateway_adapter.v1"
    adapter_id: str = Field(default_factory=lambda: f"gateway_{uuid4().hex}")
    platform: str
    mode: Literal["read_only", "draft_only", "approved_send"] = "draft_only"
    enabled: bool = False
    outbound_requires_approval: bool = True
    secret_env_vars: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

