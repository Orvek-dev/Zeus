"""Execution specification schema."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["low", "medium", "high"]


class BudgetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_wall_clock_seconds: int = 900
    max_tool_calls: int = 60
    max_cost_usd: float = 0.0
    max_network_requests: int = 0


class SandboxSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    isolation: Literal["none", "process", "container", "microvm"] = "none"
    network_policy: Literal["deny_by_default", "allowlist", "open"] = "deny_by_default"
    network_allowlist: list[str] = Field(default_factory=list)
    snapshot_required: bool = True


class WorkspaceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    allowed_paths: list[str]
    forbidden_paths: list[str]
    write_policy: Literal["read_only_until_approval", "sandbox_only", "direct"] = (
        "read_only_until_approval"
    )


class ExecutionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    title: str
    intent: str
    actions: list[str]
    expected_evidence: list[str]
    risk_level: RiskLevel = "medium"
    requires_approval: bool = False


class VerificationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    level: Literal["syntax", "behavior", "acceptance", "security", "human_review"]
    description: str
    evidence_required: list[str]


class ExecutionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["zeus.execution_spec.v1"] = "zeus.execution_spec.v1"
    run_id: str
    goal_contract_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["draft", "awaiting_approval", "approved", "rejected", "ready"] = (
        "awaiting_approval"
    )
    execution_mode: Literal["plan_only", "sandbox_after_approval"] = "plan_only"
    workspace: WorkspaceSpec
    sandbox: SandboxSpec = Field(default_factory=SandboxSpec)
    budgets: BudgetSpec = Field(default_factory=BudgetSpec)
    tools_required: list[str] = Field(default_factory=list)
    steps: list[ExecutionStep]
    verification_rules: list[VerificationRule]
    stop_conditions: list[str]
    escalation_conditions: list[str]
