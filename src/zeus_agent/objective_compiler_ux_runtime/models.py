from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

from zeus_agent.goal_intelligence_runtime.intent import IntentFrame
from zeus_agent.objective_run_runtime.models import ObjectiveRun
from zeus_agent.orchestration_runtime import DynamicWorkflowPlan

ObjectiveCompilerWorkflowDecision = Literal["compiled", "needs_interview", "blocked"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class WorkflowDagNode(BaseModel):
    model_config = _MODEL_CONFIG

    node_id: str
    depends_on: tuple[str, ...] = ()
    evidence_target: str
    owned_paths: tuple[str, ...] = ()

    @field_validator("node_id", "evidence_target")
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("depends_on", "owned_paths")
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: object) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)


class ObjectiveCompilerWorkflowResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ObjectiveCompilerWorkflowDecision
    target_version: Literal["v5.5.0"] = "v5.5.0"
    blocked_reasons: tuple[str, ...] = ()
    objective_compiler_workflow_ready: bool = True
    objective_compiler_ux_ready: bool = True
    dynamic_workflow_runtime_ready: bool = True
    objective_understood: bool = False
    interview_required: bool = False
    interview_questions: tuple[str, ...] = ()
    intent_frame: IntentFrame
    objective_run: Optional[ObjectiveRun] = None
    workflow_plan: Optional[DynamicWorkflowPlan] = None
    workflow_dag: tuple[WorkflowDagNode, ...] = ()
    selected_pattern: Optional[str] = None
    evidence_plan: tuple[str, ...] = ()
    authority_requirements: tuple[str, ...] = ()
    repair_next_steps: tuple[str, ...] = ()
    objective_contract_ready: bool = False
    workflow_dag_ready: bool = False
    evidence_plan_ready: bool = False
    authority_requirements_ready: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False
    production_ready: bool = False
    no_secret_echo: bool = True

    @field_validator(
        "blocked_reasons",
        "interview_questions",
        "evidence_plan",
        "authority_requirements",
        "repair_next_steps",
    )
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: object) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
