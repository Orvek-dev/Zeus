from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from .models import ActionRisk, require_text

_RISK_SCORE: dict[ActionRisk, int] = {
    ActionRisk.low: 0,
    ActionRisk.medium: 1,
    ActionRisk.high: 2,
}


class PlanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    plan_id: str
    task_ids: tuple[str, ...] = Field(min_length=1)
    required_capabilities: tuple[str, ...]
    acceptance_criteria: tuple[str, ...] = Field(min_length=1)
    verification_obligations: tuple[str, ...] = Field(min_length=1)
    risk: ActionRisk
    cost_units: int = Field(ge=0)

    @field_validator(
        "plan_id",
        "task_ids",
        "required_capabilities",
        "acceptance_criteria",
        "verification_obligations",
    )
    @classmethod
    def validate_text_tuple(
        cls,
        value: str | tuple[str, ...],
        info: ValidationInfo,
    ) -> str | tuple[str, ...]:
        if isinstance(value, str):
            return require_text(value, info.field_name)
        return tuple(require_text(item, info.field_name) for item in value)


class PlanTournament:
    def select(self, candidates: tuple[PlanCandidate, ...]) -> PlanCandidate:
        if not candidates:
            raise ValueError("plan_candidates_empty")
        ranked = sorted(candidates, key=_score_candidate, reverse=True)
        return ranked[0]


def _score_candidate(candidate: PlanCandidate) -> tuple[int, int, int, int]:
    return (
        len(candidate.acceptance_criteria),
        len(candidate.verification_obligations),
        -_RISK_SCORE[candidate.risk],
        -candidate.cost_units,
    )
