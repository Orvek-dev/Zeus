from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from zeus_agent.kernel.completion import CompletionSummary
from zeus_agent.kernel.contracts import GoalContract
from zeus_agent.kernel.evidence import MnemeEvidenceRecord
from zeus_agent.objective_runtime import ZeusObjectiveContract

ObjectiveRunStatus = Literal[
    "draft",
    "interviewing",
    "planned",
    "waiting_approval",
    "running",
    "verifying",
    "replanning",
    "blocked",
    "failed",
    "complete",
    "archived",
]
ObjectiveRunDecision = Literal["started", "reported", "exported", "updated", "blocked"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text


class ObjectiveRun(BaseModel):
    model_config = _MODEL_CONFIG

    objective_id: str
    run_id: str
    session_id: str
    principal_id: str
    status: ObjectiveRunStatus
    objective_contract: ZeusObjectiveContract
    goal_contract: GoalContract
    current_plan: tuple[str, ...] = ()
    active_step: Optional[str] = None
    runtime_lease_ids: tuple[str, ...] = ()
    approval_receipt_ids: tuple[str, ...] = ()
    tool_call_ids: tuple[str, ...] = ()
    provider_call_ids: tuple[str, ...] = ()
    evidence_records: tuple[MnemeEvidenceRecord, ...] = ()
    memory_candidate_ids: tuple[str, ...] = ()
    ontology_candidate_ids: tuple[str, ...] = ()
    skill_candidate_ids: tuple[str, ...] = ()
    completion_summary: CompletionSummary
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False

    @field_validator("objective_id", "run_id", "session_id", "principal_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ObjectiveRunStoreSnapshot(BaseModel):
    model_config = _MODEL_CONFIG

    runs: tuple[ObjectiveRun, ...] = Field(default_factory=tuple)


class ObjectiveRunResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ObjectiveRunDecision
    run: Optional[ObjectiveRun] = None
    blocked_reasons: tuple[str, ...] = ()
    objective_run_spine_ready: bool = True
    evidence_required_for_completion: bool = True
    authority_ledger_ready: bool = False
    live_execution_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

