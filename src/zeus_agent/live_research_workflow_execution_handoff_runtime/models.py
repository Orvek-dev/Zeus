from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowExecutionHandoffDecision = Literal["handoff_ready", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowExecutionHandoffResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowExecutionHandoffDecision
    manifest_id: Optional[str]
    handoff_ref: Optional[str]
    preflight_plan_id: Optional[str]
    authorization_id: Optional[str]
    release_id: Optional[str]
    objective_id: str
    selected_candidate_id: Optional[str]
    executor_kind: Literal["research"]
    release_ref: Optional[str]
    idempotency_key: Optional[str]
    recommended_command: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    operator_note: Optional[str] = None
    preflight_plan_bound: bool = False
    authorization_bound: bool = False
    executor_release_bound: bool = False
    operator_review_required: bool = True
    evidence_required: bool = True
    executor_release_granted: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
