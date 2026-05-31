"""Provider, model, tool, and GitHub publishing registry schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ProviderAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.provider_auth.v1"] = "zeus.provider_auth.v1"
    provider: str
    env_var: str
    base_url: str | None = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ModelRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.model_route.v1"] = "zeus.model_route.v1"
    route_id: str = Field(default_factory=lambda: f"route_{uuid4().hex}")
    purpose: str
    provider: str
    model: str
    priority: int = 100
    max_cost_usd: float = 0.0


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.tool_definition.v1"] = "zeus.tool_definition.v1"
    tool_id: str = Field(default_factory=lambda: f"tool_{uuid4().hex}")
    name: str
    description: str
    risk_level: Literal["low", "medium", "high"]
    command: list[str] = Field(default_factory=list)
    requires_approval: bool = True
    network_access: Literal["none", "allowlist", "open"] = "none"


class GitHubPublishPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.github_publish_plan.v1"] = "zeus.github_publish_plan.v1"
    plan_id: str = Field(default_factory=lambda: f"github_plan_{uuid4().hex}")
    repo: str
    remote: str = "origin"
    branch: str = "main"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    required_checks: list[str]
    blocked_until_milestones: list[int] = Field(default_factory=list)
    ready: bool = False
    notes: list[str] = Field(default_factory=list)
