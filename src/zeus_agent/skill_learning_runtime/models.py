from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)

SkillLearningDecision = Literal["report", "blocked"]
SkillLearningMemoryDecision = Literal["recorded", "blocked"]


class SkillLearningResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SkillLearningDecision
    eval_record_count: int
    learning_candidate_count: int
    ready_learning_count: int
    blocked_learning_count: int
    review_required_count: int
    promoted_candidate_count: int
    selected_learning: Optional[dict[str, JsonValue]] = None
    learning_candidates: tuple[dict[str, JsonValue], ...] = Field(default_factory=tuple)
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    active_skill_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class SkillLearningMemoryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SkillLearningMemoryDecision
    selected_learning: Optional[dict[str, JsonValue]] = None
    selected_fact: Optional[dict[str, JsonValue]] = None
    learning_candidate_count: int
    fact_count: int
    quarantined_count: int
    blocked_reasons: tuple[str, ...] = ()
    memory_store_local: bool = True
    retention_policy: str = "local_review_required"
    memory_promoted: bool = False
    wiki_page_written: bool = False
    active_skill_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
