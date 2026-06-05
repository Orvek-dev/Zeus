from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

BundleReviewDecision = Literal["review_ready", "operator_input_required", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowBundleReviewResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: BundleReviewDecision
    review_id: Optional[str]
    review_ref: str
    bundle_id: Optional[str]
    status_id: Optional[str]
    objective_id: str
    source_review_count: int
    review_ready_source_count: int
    endpoint_required_count: int
    external_review_required_count: int
    blocked_source_count: int
    blocked_reasons: tuple[str, ...] = ()
    required_operator_actions: tuple[str, ...] = ()
    network_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
