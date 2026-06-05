from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)

SkillEvalDecision = Literal["evaluated", "blocked"]
SkillEvalStatus = Literal["ready_for_review", "blocked"]


class SkillEvalCheck(BaseModel):
    model_config = _MODEL_CONFIG

    check_id: str
    passed: bool
    points: int
    reason: str


class SkillEvalResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SkillEvalDecision
    eval_status: SkillEvalStatus
    candidate_id: Optional[str]
    generated_candidate_id: Optional[str] = None
    source: Optional[str] = None
    source_candidate_id: Optional[str] = None
    source_record_id: Optional[str] = None
    score: int = 0
    checks: tuple[SkillEvalCheck, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    promotion_allowed: bool = False
    active_skill_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
