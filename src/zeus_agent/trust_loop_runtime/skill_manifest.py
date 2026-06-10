from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import require_text


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    skill_id: str
    allowed_capabilities: tuple[str, ...] = Field(min_length=1)

    @field_validator("skill_id")
    @classmethod
    def validate_skill_id(cls, value: str) -> str:
        return require_text(value, "skill_id")

    @field_validator("allowed_capabilities")
    @classmethod
    def validate_capabilities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(require_text(value, "allowed_capabilities") for value in values)

    def allows(self, capability_id: str) -> bool:
        return capability_id in set(self.allowed_capabilities)
