from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.objective_risk_runtime import Triage
from zeus_agent.workflow_fabric_runtime import DecisionRecord


class CostEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    per_run_units: int = Field(ge=0)
    projected_runs: Optional[int] = Field(default=None, ge=0)
    projected_total_units: Optional[int] = Field(default=None, ge=0)
    budget_cap_units: Optional[int] = Field(default=None, ge=0)
    within_budget: bool = True


class ApprovalStage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    node_id: str
    side_effect: str
    manual_approvals_remaining: int = Field(ge=0)


class ObjectiveCard(BaseModel):
    """The single rendered surface: objective -> plan + questions + cost + gaps.

    Side-effect-free product of compilation. The same card drives CLI, TUI, and
    web; every assumption, question, and decision is carried so the trace graph
    can later answer "why did it run this way?".
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    normalized_objective: str
    triage: Triage
    decision: str
    chosen_workflow_id: Optional[str]
    workflow_node_ids: tuple[str, ...]
    questions: tuple[str, ...]
    assumptions: tuple[str, ...]
    capability_gaps: tuple[str, ...]
    approval_stages: tuple[ApprovalStage, ...]
    cost: CostEstimate
    blocking_question_count: int = Field(ge=0)
    proceed_allowed_without_answers: bool
    decision_record: DecisionRecord
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
