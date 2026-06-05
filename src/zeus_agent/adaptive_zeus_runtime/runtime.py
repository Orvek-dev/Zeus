from __future__ import annotations

import json
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from zeus_agent.orchestration_runtime import (
    DynamicWorkflowCompiler,
    WorkflowCompileRequest,
    WorkflowPattern,
)


AdaptiveZeusDecision = Literal["report", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_TARGET_VERSION: Final = "v0.10.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v0.10.0.adaptive_zeus"
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)


class AdaptiveZeusContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: AdaptiveZeusDecision
    target_version: str
    objective_contract_id: str
    selected_objective: str
    selected_pattern: WorkflowPattern
    why_not_decision: str
    pattern_changed_from_default: bool
    parallel_wave_count: int
    parallel_task_count: int
    parallel_schedule: dict[str, JsonValue]
    critique_checkpoint: dict[str, JsonValue]
    rejected_alternatives: tuple[WorkflowPattern, ...]
    review_required: bool
    safety_notes: tuple[str, ...]
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    raw_secret_marker_detected: bool = False
    adaptive_zeus_ready: bool = False
    workflow_self_modification: bool = False
    workflow_memory_auto_write: bool = False
    workflow_memory_write_performed: bool = False
    workflow_pattern_promoted: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> AdaptiveZeusContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_adaptive_zeus_contract(
    *,
    objective: str,
    task_count: int = 1,
    requires_code: bool = False,
    requires_research: bool = False,
    risk_level: str = "normal",
    evidence_target: str = "v010.adaptive_zeus",
) -> AdaptiveZeusContract:
    if _has_secret_marker(objective):
        return _blocked_contract(
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        ).with_secret_scan()

    try:
        request = WorkflowCompileRequest(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=evidence_target,
        )
    except ValidationError:
        return _blocked_contract(blocked_reasons=("malformed_adaptive_workflow_request",)).with_secret_scan()

    plan = DynamicWorkflowCompiler().compile(request)
    parallel_schedule = plan.parallel_schedule.model_dump(mode="json")
    critique_checkpoint = plan.critique_checkpoint.model_dump(mode="json")
    decision: AdaptiveZeusDecision = "report" if plan.decision == "compiled" else "blocked"
    result = AdaptiveZeusContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        selected_objective=plan.normalized_objective if decision == "report" else "unknown",
        selected_pattern=plan.selected_pattern,
        why_not_decision=plan.why_not_decision,
        pattern_changed_from_default=plan.selected_pattern != "classify_and_act",
        parallel_wave_count=len(plan.parallel_schedule.waves),
        parallel_task_count=sum(len(wave.task_ids) for wave in plan.parallel_schedule.waves),
        parallel_schedule=parallel_schedule,
        critique_checkpoint=critique_checkpoint,
        rejected_alternatives=plan.critique_checkpoint.rejected_alternatives,
        review_required=plan.review_required,
        safety_notes=_safety_notes(plan.safety_notes),
        blocked_reasons=plan.blocked_reasons,
        recommended_next_commands=_recommended_next_commands(plan.selected_pattern),
        raw_secret_marker_detected=False,
        adaptive_zeus_ready=False,
        workflow_self_modification=False,
        workflow_memory_auto_write=False,
        workflow_memory_write_performed=plan.critique_checkpoint.memory_write_performed,
        workflow_pattern_promoted=False,
        authority_widened=plan.authority_widened or plan.critique_checkpoint.authority_widened,
        credential_material_accessed=False,
        network_opened=plan.network_opened or plan.critique_checkpoint.network_opened,
        external_delivery_opened=False,
        handler_executed=plan.handler_executed,
        live_production_claimed=plan.live_production_claimed or plan.critique_checkpoint.live_production_claimed,
    )
    return result.with_secret_scan()


def _blocked_contract(
    *,
    blocked_reasons: tuple[str, ...],
    raw_secret_marker_detected: bool = False,
) -> AdaptiveZeusContract:
    return AdaptiveZeusContract(
        decision="blocked",
        target_version=_TARGET_VERSION,
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        selected_objective="unknown",
        selected_pattern="blocked",
        why_not_decision="blocked",
        pattern_changed_from_default=False,
        parallel_wave_count=0,
        parallel_task_count=0,
        parallel_schedule={
            "decision": "blocked",
            "reason": "adaptive_zeus_preflight_blocked",
            "waves": [],
            "blocked_reasons": list(blocked_reasons),
            "handler_executed": False,
            "network_opened": False,
            "dry_run": True,
        },
        critique_checkpoint={
            "objective_id": "unknown",
            "starting_pattern": "blocked",
            "critique_question": "Why not stop before unsafe workflow adaptation?",
            "adaptation_decision": "blocked",
            "evidence_target": "v010.adaptive_zeus",
            "rejected_alternatives": [],
            "reusable_lesson_candidate": "Block unsafe adaptive workflow inputs before planning.",
            "memory_write_performed": False,
            "authority_widened": False,
            "network_opened": False,
            "live_production_claimed": False,
        },
        rejected_alternatives=(),
        review_required=True,
        safety_notes=_safety_notes(("adaptive_workflow_preflight_blocked",)),
        blocked_reasons=blocked_reasons,
        recommended_next_commands=(),
        raw_secret_marker_detected=raw_secret_marker_detected,
        adaptive_zeus_ready=False,
        workflow_self_modification=False,
        workflow_memory_auto_write=False,
        workflow_memory_write_performed=False,
        workflow_pattern_promoted=False,
        authority_widened=False,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )


def _safety_notes(notes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *notes,
                "workflow_self_modification_disabled",
                "workflow_memory_auto_write_disabled",
                "no_authority_widening_from_adaptive_choice",
                "no_live_execution_from_adaptive_choice",
            )
        )
    )


def _recommended_next_commands(pattern: WorkflowPattern) -> tuple[str, ...]:
    if pattern == "fan_out_and_synthesize":
        return (
            "split disjoint write scopes before worker launch",
            "run worker-local RED/GREEN evidence before integration",
            "synthesize under orchestrator-owned integration tests",
        )
    if pattern == "adversarial_verification":
        return (
            "capture implementation evidence",
            "run independent adversarial review before completion",
        )
    if pattern == "lean_ulw":
        return (
            "keep one controlled work lane",
            "run focused validation before close",
        )
    if pattern == "blocked":
        return ()
    return (
        "classify the objective contract",
        "execute the narrowest sufficient workflow",
    )


def _has_secret_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
