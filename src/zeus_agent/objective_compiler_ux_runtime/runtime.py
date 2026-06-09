from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from zeus_agent.goal_intelligence_runtime.intent import (
    IntentFrame,
    build_intent_frame,
    interview_questions_for,
)
from zeus_agent.objective_compiler_ux_runtime.models import (
    ObjectiveCompilerWorkflowResult,
    WorkflowDagNode,
)
from zeus_agent.objective_run_runtime import ObjectiveRunRuntime, ObjectiveRunStore
from zeus_agent.orchestration_runtime import DynamicWorkflowCompiler, DynamicWorkflowPlan, WorkflowCompileRequest


def build_objective_compiler_workflow(
    *,
    home: Path,
    objective: str,
    session_id: str = "default",
    principal_id: str = "operator.local",
    task_count: int = 1,
    requires_code: bool = False,
    requires_research: bool = False,
    risk_level: str = "normal",
    interview_answers: tuple[str, ...] = (),
    cognitive_provider_output: Optional[str] = None,
) -> ObjectiveCompilerWorkflowResult:
    intent_result = build_intent_frame(
        objective=objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        interview_answers=interview_answers,
        cognitive_provider_output=cognitive_provider_output,
    )
    frame = intent_result.frame
    questions = interview_questions_for(frame)
    blocked_reasons = tuple(intent_result.blocked_reasons)
    if blocked_reasons:
        return _blocked_result(frame=frame, blocked_reasons=blocked_reasons)
    if not frame.understood:
        return ObjectiveCompilerWorkflowResult(
            decision="needs_interview",
            objective_understood=False,
            interview_required=True,
            interview_questions=questions,
            intent_frame=frame,
            repair_next_steps=_repair_steps(frame),
            no_secret_echo=True,
        )

    objective_runtime = ObjectiveRunRuntime(ObjectiveRunStore(home))
    started = objective_runtime.start(
        objective=frame.desired_outcome,
        session_id=session_id,
        principal_id=principal_id,
        acceptance_criteria=frame.acceptance_criteria,
        constraints=frame.constraints,
    )
    if started.run is None:
        return _blocked_result(frame=frame, blocked_reasons=started.blocked_reasons)

    workflow = DynamicWorkflowCompiler().compile(
        WorkflowCompileRequest(
            objective=frame.desired_outcome,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=_evidence_target(frame),
        )
    )
    if workflow.decision == "blocked":
        return ObjectiveCompilerWorkflowResult(
            decision="blocked",
            blocked_reasons=workflow.blocked_reasons,
            objective_understood=True,
            intent_frame=frame,
            objective_run=started.run,
            workflow_plan=workflow,
            selected_pattern=workflow.selected_pattern,
            evidence_plan=frame.acceptance_criteria,
            authority_requirements=_authority_requirements(frame, risk_level),
            repair_next_steps=_workflow_repair_steps(workflow),
            objective_contract_ready=True,
            evidence_plan_ready=bool(frame.acceptance_criteria),
            authority_requirements_ready=True,
        )

    dag = _workflow_dag(workflow)
    authority = _authority_requirements(frame, risk_level)
    return ObjectiveCompilerWorkflowResult(
        decision="compiled",
        objective_understood=True,
        interview_required=False,
        intent_frame=frame,
        objective_run=started.run,
        workflow_plan=workflow,
        workflow_dag=dag,
        selected_pattern=workflow.selected_pattern,
        evidence_plan=frame.acceptance_criteria,
        authority_requirements=authority,
        repair_next_steps=(),
        objective_contract_ready=True,
        workflow_dag_ready=bool(dag),
        evidence_plan_ready=bool(frame.acceptance_criteria),
        authority_requirements_ready=bool(authority),
    )


def _blocked_result(
    *,
    frame: IntentFrame,
    blocked_reasons: tuple[str, ...],
) -> ObjectiveCompilerWorkflowResult:
    return ObjectiveCompilerWorkflowResult(
        decision="blocked",
        blocked_reasons=blocked_reasons,
        objective_understood=False,
        interview_required=False,
        intent_frame=frame,
        repair_next_steps=("Repair blocked cognitive or objective input before workflow planning.",),
    )


def _workflow_dag(workflow: DynamicWorkflowPlan) -> tuple[WorkflowDagNode, ...]:
    nodes: list[WorkflowDagNode] = []
    previous_wave_task_ids: tuple[str, ...] = ()
    for wave in workflow.parallel_schedule.waves:
        for task_id in wave.task_ids:
            nodes.append(
                WorkflowDagNode(
                    node_id=task_id,
                    depends_on=previous_wave_task_ids,
                    evidence_target=workflow.critique_checkpoint.evidence_target,
                    owned_paths=(),
                )
            )
        previous_wave_task_ids = wave.task_ids
    return tuple(nodes)


def _authority_requirements(frame: IntentFrame, risk_level: str) -> tuple[str, ...]:
    requirements = ["objective_run_id", "evidence_target"]
    lowered = " ".join((frame.desired_outcome, *frame.constraints)).lower()
    if risk_level == "high" or "approval" in lowered or "live" in lowered:
        requirements.extend(
            [
                "runtime_lease",
                "human_approval",
                "credential_scope_or_secret_ref",
                "sandbox_policy",
                "audit_receipt",
                "rollback_plan",
            ]
        )
    return tuple(dict.fromkeys(requirements))


def _repair_steps(frame: IntentFrame) -> tuple[str, ...]:
    steps = []
    if "desired_outcome" in frame.unknowns:
        steps.append("Clarify the concrete outcome before compiling a workflow.")
    if "acceptance_criteria" in frame.unknowns:
        steps.append("Provide observable completion evidence or acceptance criteria.")
    if "risk_boundary" in frame.unknowns:
        steps.append("Define approval, lease, audit, and rollback boundaries for risky actions.")
    if "constraints" in frame.unknowns:
        steps.append("Name constraints that should bound the workflow.")
    return tuple(dict.fromkeys(steps))


def _workflow_repair_steps(workflow: DynamicWorkflowPlan) -> tuple[str, ...]:
    return tuple(
        "Repair workflow blocker: {0}".format(reason) for reason in workflow.blocked_reasons
    )


def _evidence_target(frame: IntentFrame) -> str:
    digest = hashlib.sha256(frame.desired_outcome.encode("utf-8")).hexdigest()
    return "objective_compiler_workflow.{0}".format(digest[:12])
