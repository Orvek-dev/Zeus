from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchExecutionPlanResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["planned", "blocked"]
    execution_id: Optional[str]
    execution_ref: str
    adapter_id: Optional[str]
    source_id: Optional[str]
    endpoint: Optional[str]
    policy_id: Optional[str]
    source_config_id: Optional[str]
    source_pin_ref: Optional[str]
    max_results: Optional[int]
    rate_limit_per_minute: Optional[int]
    blocked_reasons: tuple[str, ...] = ()
    source_config_bound: bool = False
    activation_policy_bound: bool = False
    endpoint_bound: bool = False
    source_pin_bound: bool = False
    approval_bound: bool = False
    live_search_allowed: bool = False
    real_fetcher_available: bool = False
    production_fetcher_configured: bool = False
    network_opened: bool = False
    client_constructed: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
