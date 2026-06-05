from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanResult
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigResult

BundleDecision = Literal["bundle_planned", "blocked"]
BundleSourceState = Literal["planned", "endpoint_required", "blocked"]
_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchWorkflowSourcePlan(BaseModel):
    model_config = _MODEL_CONFIG

    adapter_id: str
    source_id: str
    state: BundleSourceState
    endpoint: Optional[str]
    source_config: Optional[LiveResearchSourceConfigResult] = None
    activation_policy: Optional[LiveResearchActivationPolicyResult] = None
    execution_plan: Optional[LiveResearchExecutionPlanResult] = None
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    live_production_claimed: bool = False


class LiveResearchWorkflowBundleResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: BundleDecision
    bundle_id: Optional[str]
    bundle_ref: str
    workflow_plan_id: Optional[str]
    objective_id: str
    query: str
    source_plan_count: int
    planned_source_count: int
    endpoint_required_count: int
    source_plans: tuple[LiveResearchWorkflowSourcePlan, ...]
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
