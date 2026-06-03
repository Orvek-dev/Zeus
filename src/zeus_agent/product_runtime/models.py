from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from zeus_agent.product_runtime.domain_language import (
    CoreDomainLanguageSummary,
    core_domain_language_summary,
)


class WorkLoopContractAdapter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_contract_id: str
    normalized_goal: str
    deliverables: list[str]
    acceptance_criteria: list[str]


class ProductRuntimeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    core_domain_language: CoreDomainLanguageSummary = Field(
        default_factory=core_domain_language_summary,
    )
    objective_compiled: bool
    objective_id: str
    work_loop_plan_created: bool
    work_loop_id: str
    orchestration_lane_count: int
    verification_obligations: int
    verification_completion_allowed: bool
    promotion_live_transport: bool
    promotion_decision: str
    promotion_reason: str
    handler_executed: bool
    network_opened: bool
    skill_evolution_candidate_status: str
    skill_evolution_promoted: bool
    blocked_reasons: list[str]
    adjacent_surface_still_works: bool
    no_secret_echo: bool
