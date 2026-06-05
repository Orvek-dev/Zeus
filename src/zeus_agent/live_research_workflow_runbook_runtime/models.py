from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RunbookDecision = Literal["runbook_ready", "blocked"]
RunbookStepState = Literal["operator_action", "ready", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowRunbookStep(BaseModel):
    model_config = _MODEL_CONFIG

    step_id: str
    state: RunbookStepState
    operator_action: str
    recommended_command: str
    evidence_required: bool = True
    network_opened: bool = False
    live_production_claimed: bool = False


class LiveResearchWorkflowRunbookResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RunbookDecision
    runbook_id: Optional[str]
    runbook_ref: str
    review_id: Optional[str]
    review_ref: str
    objective_id: str
    review_decision: str
    step_count: int
    steps: tuple[LiveResearchWorkflowRunbookStep, ...]
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
