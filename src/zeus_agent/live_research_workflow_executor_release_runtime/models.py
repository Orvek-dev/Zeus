from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

ResearchWorkflowExecutorReleaseDecision = Literal["release_ready", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowExecutorReleaseResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ResearchWorkflowExecutorReleaseDecision
    release_id: Optional[str]
    authorization_id: Optional[str]
    authorization_ref: Optional[str]
    selected_candidate_id: Optional[str]
    executor_kind: Literal["research"]
    release_ref: Optional[str]
    idempotency_key: str
    blocked_reasons: tuple[str, ...] = ()
    release_envelope_ready: bool = False
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
