from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zeus_agent.objective_risk_runtime import Triage, Unknown
from zeus_agent.workflow_fabric_runtime import WorkflowCandidate

from .compiler import compile_objective_card
from .models import ObjectiveCard


class ObjectiveFrameInput(BaseModel):
    """The structured frame the cognitive layer (an LLM) produces for an utterance.

    This is the contract at the LLM boundary: the model returns unknowns and
    candidate workflows; everything downstream is deterministic. Validated
    strictly so a malformed frame fails closed instead of silently degrading.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    normalized_objective: str
    triage: Triage
    unknowns: tuple[Unknown, ...] = ()
    candidates: tuple[WorkflowCandidate, ...] = Field(min_length=1)
    required_criteria: tuple[str, ...] = ()
    budget_cap_units: Optional[int] = Field(default=None, ge=0)
    projected_runs: Optional[int] = Field(default=None, ge=0)
    override_just_do_it: bool = False

    @field_validator("normalized_objective")
    @classmethod
    def validate_objective(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("normalized_objective_empty")
        return normalized


def compile_from_frame(frame: ObjectiveFrameInput) -> ObjectiveCard:
    return compile_objective_card(
        normalized_objective=frame.normalized_objective,
        triage=frame.triage,
        unknowns=frame.unknowns,
        candidates=frame.candidates,
        required_criteria=frame.required_criteria,
        budget_cap_units=frame.budget_cap_units,
        projected_runs=frame.projected_runs,
        override_just_do_it=frame.override_just_do_it,
    )
