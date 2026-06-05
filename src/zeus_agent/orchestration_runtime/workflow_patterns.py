from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from zeus_agent.objective_runtime import ObjectiveCompiler

from .models import ParallelSchedule, ParallelTaskSpec
from .scheduler import ParallelScheduler
from .workflow_critique import (
    MODEL_CONFIG,
    WorkflowCritiqueCheckpoint,
    WorkflowDecision,
    WorkflowPattern,
    WorkflowRiskLevel,
    WhyNotDecision,
    build_critique_checkpoint,
)


class WorkflowCompileRequest(BaseModel):
    model_config = MODEL_CONFIG

    objective: str
    task_count: int = Field(default=1, ge=1)
    requires_code: bool = False
    requires_research: bool = False
    risk_level: WorkflowRiskLevel = "normal"
    evidence_target: str

    @field_validator("objective", "evidence_target")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("workflow_field_empty")
        return normalized


class DynamicWorkflowPlan(BaseModel):
    model_config = MODEL_CONFIG

    decision: WorkflowDecision
    selected_pattern: WorkflowPattern
    why_not_decision: WhyNotDecision
    objective_id: str
    normalized_objective: str
    parallel_schedule: ParallelSchedule
    critique_checkpoint: WorkflowCritiqueCheckpoint
    review_required: bool
    safety_notes: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    live_production_claimed: bool = False
    authority_widened: bool = False
    network_opened: bool = False
    handler_executed: bool = False


class DynamicWorkflowCompiler:
    def compile(self, request: WorkflowCompileRequest) -> DynamicWorkflowPlan:
        contract = ObjectiveCompiler().compile(request.objective)
        if contract.blocked:
            return DynamicWorkflowPlan(
                decision="blocked",
                selected_pattern="blocked",
                why_not_decision="blocked",
                objective_id=contract.objective_id,
                normalized_objective=contract.normalized_objective,
                parallel_schedule=_blocked_schedule(tuple(contract.block_reasons)),
                critique_checkpoint=_critique_checkpoint(
                    objective_id=contract.objective_id,
                    pattern="blocked",
                    request=request,
                ),
                review_required=True,
                safety_notes=("objective_compiler_blocked",),
                blocked_reasons=tuple(contract.block_reasons),
            )

        pattern = _select_pattern(request)
        tasks = _tasks_for_pattern(pattern, request)
        schedule = ParallelScheduler().plan(tasks)
        safety_notes = _safety_notes(pattern, request, schedule)
        return DynamicWorkflowPlan(
            decision="compiled" if schedule.decision == "planned" else "blocked",
            selected_pattern=pattern if schedule.decision == "planned" else "blocked",
            why_not_decision=_why_not_decision(pattern, request) if schedule.decision == "planned" else "blocked",
            objective_id=contract.objective_id,
            normalized_objective=contract.normalized_objective,
            parallel_schedule=schedule,
            critique_checkpoint=_critique_checkpoint(
                objective_id=contract.objective_id,
                pattern=pattern if schedule.decision == "planned" else "blocked",
                request=request,
            ),
            review_required=_review_required(pattern, request),
            safety_notes=safety_notes,
            blocked_reasons=schedule.blocked_reasons,
        )


def _select_pattern(request: WorkflowCompileRequest) -> WorkflowPattern:
    if request.risk_level == "high":
        return "adversarial_verification"
    if request.task_count >= 4 or (request.requires_code and request.requires_research):
        return "fan_out_and_synthesize"
    if request.task_count <= 2 and request.risk_level == "low":
        return "lean_ulw"
    return "classify_and_act"


def _tasks_for_pattern(
    pattern: WorkflowPattern,
    request: WorkflowCompileRequest,
) -> tuple[ParallelTaskSpec, ...]:
    if pattern == "adversarial_verification":
        return (
            _task("implementation-slice", ("src/zeus_agent/**",), request.evidence_target),
            _task("adversarial-review", ("harness/reviews/**",), request.evidence_target, depends_on=("implementation-slice",)),
        )
    if pattern == "fan_out_and_synthesize":
        return (
            _task("code-slice-a", ("src/zeus_agent/runtime_a/**",), request.evidence_target),
            _task("code-slice-b", ("src/zeus_agent/runtime_b/**",), request.evidence_target),
            _task("verification-slice", ("tests/runtime_slices/**",), request.evidence_target),
            _task("integration-synthesis", ("docs/ai/current/Implement.md",), request.evidence_target, depends_on=("code-slice-a", "code-slice-b", "verification-slice")),
        )
    if pattern == "lean_ulw":
        return (_task("lean-main", ("src/zeus_agent/**",), request.evidence_target),)
    return (
        _task("classify", ("docs/ai/current/Plan.md",), request.evidence_target),
        _task("act", ("src/zeus_agent/**",), request.evidence_target, depends_on=("classify",)),
    )


def _task(
    task_id: str,
    owned_paths: tuple[str, ...],
    evidence_target: str,
    *,
    depends_on: tuple[str, ...] = (),
) -> ParallelTaskSpec:
    return ParallelTaskSpec(
        task_id=task_id,
        owned_paths=owned_paths,
        depends_on=depends_on,
        evidence_target=evidence_target,
        manual_qa_channel="script-pty",
        subagent_depth=1,
        live_capable=False,
        security_decisions=(),
    )


def _review_required(pattern: WorkflowPattern, request: WorkflowCompileRequest) -> bool:
    return pattern == "adversarial_verification" or request.risk_level == "high"


def _why_not_decision(pattern: WorkflowPattern, request: WorkflowCompileRequest) -> WhyNotDecision:
    if pattern == "fan_out_and_synthesize":
        return "fan_out"
    if pattern == "adversarial_verification":
        return "adversarial_review"
    if pattern == "lean_ulw":
        return "lean_down"
    return "continue"


def _critique_checkpoint(
    *,
    objective_id: str,
    pattern: WorkflowPattern,
    request: WorkflowCompileRequest,
) -> WorkflowCritiqueCheckpoint:
    return build_critique_checkpoint(
        objective_id=objective_id,
        pattern=pattern,
        risk_level=request.risk_level,
        task_count=request.task_count,
        requires_code=request.requires_code,
        requires_research=request.requires_research,
        evidence_target=request.evidence_target,
    )


def _safety_notes(
    pattern: WorkflowPattern,
    request: WorkflowCompileRequest,
    schedule: ParallelSchedule,
) -> tuple[str, ...]:
    notes: list[str] = []
    if pattern == "adversarial_verification" or request.risk_level == "high":
        notes.append("high_risk_requires_independent_review")
    if pattern == "fan_out_and_synthesize":
        notes.append("disjoint_write_scopes_required")
    if schedule.decision == "blocked":
        notes.extend(schedule.blocked_reasons)
    notes.append("no_authority_widening_from_workflow_choice")
    return tuple(dict.fromkeys(notes))


def _blocked_schedule(reasons: tuple[str, ...]) -> ParallelSchedule:
    return ParallelSchedule(
        decision="blocked",
        reason="objective_compiler_blocked",
        waves=(),
        blocked_reasons=reasons,
        handler_executed=False,
        network_opened=False,
        dry_run=True,
    )


__all__ = [
    "DynamicWorkflowCompiler",
    "DynamicWorkflowPlan",
    "WorkflowCompileRequest",
    "WorkflowCritiqueCheckpoint",
    "WorkflowDecision",
    "WorkflowPattern",
]
