from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from zeus_agent.security.credentials import redact_secret_like

ObjectiveStatus = Literal["compiled", "blocked"]
AuthorityPosture = Literal["plan_only", "blocked"]


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text


def _redact_value(value: str) -> str:
    return redact_secret_like(value)


class VerificationObligation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    requirement_id: str
    description: str
    evidence_target: str

    @field_validator("obligation_id", "requirement_id", "description", "evidence_target")
    @classmethod
    def _validate_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)


class ZeusObjectiveContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_id: str
    raw_user_request: str
    normalized_objective: str
    deliverables: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    authority_posture: AuthorityPosture
    verification_obligations: List[VerificationObligation] = Field(default_factory=list)
    blocked: bool
    status: ObjectiveStatus
    block_reasons: List[str] = Field(default_factory=list)
    prompt_injection_detected: bool
    no_secret_echo: bool

    @field_validator("objective_id")
    @classmethod
    def _validate_objective_id(cls, value: str) -> str:
        return _require_non_empty(value, "objective_id")

    @field_validator("deliverables", "constraints", "block_reasons")
    @classmethod
    def _validate_string_lists(cls, values: List[str], info: object) -> List[str]:
        return [_require_non_empty(value, info.field_name) for value in values]

    @field_serializer("raw_user_request", "normalized_objective")
    def _serialize_redacted_text(self, value: str) -> str:
        return _redact_value(value)

    @field_serializer("deliverables", "constraints", "block_reasons")
    def _serialize_redacted_list(self, values: List[str]) -> List[str]:
        return [_redact_value(value) for value in values]
