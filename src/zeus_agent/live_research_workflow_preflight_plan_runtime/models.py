from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

PreflightPlanDecision = Literal["preflight_candidate_ready", "operator_action_required", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowPreflightCandidate(BaseModel):
    model_config = _MODEL_CONFIG

    candidate_id: str
    executor_kind: Literal["research"]
    runbook_step_id: str
    preflight_ref: str
    recommended_command: str
    operator_review_required: bool = True
    evidence_required: bool = True
    network_opened: bool = False
    live_production_claimed: bool = False


class LiveResearchWorkflowPreflightPlanResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: PreflightPlanDecision
    preflight_plan_id: Optional[str]
    preflight_ref: str
    runbook_id: Optional[str]
    runbook_ref: str
    objective_id: str
    preflight_candidate_count: int
    required_operator_action_count: int
    preflight_candidates: tuple[LiveResearchWorkflowPreflightCandidate, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
