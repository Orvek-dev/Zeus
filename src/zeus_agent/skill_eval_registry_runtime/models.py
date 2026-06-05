from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

SkillEvalRegistryDecision = Literal["recorded", "listed", "blocked"]


class SkillEvalRegistryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SkillEvalRegistryDecision
    eval_record_id: Optional[str] = None
    eval_ref: Optional[str] = None
    record_path: str
    candidate_id: Optional[str] = None
    eval_status: Optional[str] = None
    source: Optional[str] = None
    record_count: int = 0
    ready_for_review_count: int = 0
    blocked_eval_count: int = 0
    records: tuple[dict[str, JsonValue], ...] = Field(default_factory=tuple)
    blocked_reasons: tuple[str, ...] = ()
    promotion_allowed: bool = False
    active_skill_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
