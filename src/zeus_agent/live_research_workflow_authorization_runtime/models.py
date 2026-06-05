from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowAuthorizationDecision = Literal[
    "authorization_ready",
    "operator_action_required",
    "blocked",
]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowAuthorizationResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowAuthorizationDecision
    authorization_id: Optional[str]
    authorization_ref: Optional[str]
    preflight_plan_id: Optional[str]
    preflight_ref: str
    objective_id: str
    preflight_candidate_count: int
    authorized_candidate_count: int
    selected_candidate_id: Optional[str]
    operator_approval_ref: Optional[str]
    evidence_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    authorization_envelope_ready: bool = False
    authorization_bound: bool = False
    operator_approval_bound: bool = False
    evidence_bound: bool = False
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

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
