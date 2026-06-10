from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class RiskClass(str, Enum):
    """The six domain-independent risk families an unknown can belong to.

    The classifier never needs domain knowledge: a blog publish target and a
    bank transfer target are both ``external`` instances; a monthly spend cap
    and an API budget are both ``cost`` instances. Question-vs-assume policy is
    derived from the class, not from the topic.
    """

    external = "external"
    cost = "cost"
    access = "access"
    quality = "quality"
    time = "time"
    data = "data"


class BlastRadius(str, Enum):
    local = "local"
    account = "account"
    public = "public"


class Irreversibility(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Resolution(str, Enum):
    question = "question"
    assume = "assume"
    learn_by_sample = "learn_by_sample"
    defer = "defer"


class Triage(str, Enum):
    chat = "chat"
    oneshot = "oneshot"
    project = "project"
    automation = "automation"


class SafeDefault(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    value: str
    rationale: str

    @field_validator("value", "rationale")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class Unknown(BaseModel):
    """A single missing fact extracted from an objective.

    The semantic fields (``risk_class``, ``irreversibility`` ...) are filled by
    the cognitive layer (an LLM). Whether the unknown becomes a question, an
    assumption, a sample-learned value, or a deferred decision is computed
    deterministically by Zeus from these fields — never hardcoded per domain.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    unknown_id: str
    description: str
    risk_class: RiskClass
    irreversibility: Irreversibility = Irreversibility.low
    blast_radius: BlastRadius = BlastRadius.local
    cost_bucket: int = Field(default=1, ge=1, le=5)
    failure_probability: float = Field(default=0.5, ge=0.0, le=1.0)
    safe_default: Optional[SafeDefault] = None
    sample_learnable: bool = False
    deferrable: bool = False
    # Cross-class signals (set by the cognitive layer / graph analysis).
    multiple_account_candidates: bool = False
    sensitive: bool = False
    feeds_external_sink: bool = False
    question_text: Optional[str] = None

    @field_validator("unknown_id", "description")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)

    @field_validator("question_text")
    @classmethod
    def validate_optional_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return require_text(value, info.field_name)


class RiskContext(BaseModel):
    """Workflow-level numeric context used by cross-class escalation rules.

    ``budget_cap_units is None`` means the user never set a spend cap — which is
    itself a fail-closed trigger for any ``cost`` unknown.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    projected_cost_units: int = Field(default=0, ge=0)
    budget_cap_units: Optional[int] = Field(default=None, ge=0)
    sample_cost_units: int = Field(default=0, ge=0)
    single_run_cap_units: int = Field(default=8, ge=0)


class UnknownResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    unknown_id: str
    risk_class: RiskClass
    resolution: Resolution
    voi_score: float
    threshold: float
    override_locked: bool
    reasons: tuple[str, ...]
    question: Optional[str] = None
    assumed_value: Optional[str] = None

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("reasons_empty")
        return tuple(require_text(value, "reasons") for value in values)


class ObjectiveRiskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    triage: Triage
    resolutions: tuple[UnknownResolution, ...]
    questions: tuple[str, ...]
    assumptions: tuple[str, ...]
    blocking_question_count: int = Field(ge=0)
    proceed_allowed_without_answers: bool
    override_applied: bool = False
