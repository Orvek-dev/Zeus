"""Sisyphus goal runner.

The runner advances an approved run as far as the current local evidence allows.
It does not pretend work is done: blocked implementation steps become explicit
escalations rather than silent success.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from zeus_agent.core.mneme import diff_gate, record_checkpoint_evidence, record_evidence
from zeus_agent.runtime.sandbox import SandboxRuntime, SandboxPolicyError
from zeus_agent.schemas.sisyphus import RunStepResult, SisyphusRunReport
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import write_private_json
from zeus_agent.storage.run_store import RunStore


class SisyphusBlocked(RuntimeError):
    """Raised when a run cannot advance without user or tool input."""


def pursue_run(run_id: str, *, home: Path | None = None, max_iterations: int = 1) -> SisyphusRunReport:
    store = RunStore(home)
    contract = store.load_goal_contract(run_id)
    spec = store.load_execution_spec(run_id)
    if contract.approval_state != "approved":
        raise SisyphusBlocked("Sisyphus requires an approved blueprint")

    started_at = datetime.now(UTC)
    step_results: list[RunStepResult] = []
    escalation_reasons: list[str] = []
    runtime = SandboxRuntime(home)

    intent_evidence = record_evidence(
        run_id,
        "note",
        "Intent locked from approved GoalContract.",
        passed=True,
        payload={
            "goal_id": contract.goal_id,
            "deliverables": contract.deliverables,
            "acceptance_criteria_count": len(contract.acceptance_criteria),
        },
        home=home,
    )
    step_results.append(
        RunStepResult(
            step_id="step_1_intent_lock",
            title="Lock Intent",
            status="completed",
            evidence_ids=[intent_evidence.evidence_id],
            notes=["Approved contract is the source of truth."],
        )
    )

    try:
        checkpoint = runtime.create_checkpoint(run_id)
        checkpoint_evidence = record_checkpoint_evidence(run_id, checkpoint, home=home)
        step_results.append(
            RunStepResult(
                step_id="step_2_readonly_inspection",
                title="Read-only Inspection",
                status="completed",
                evidence_ids=[checkpoint_evidence.evidence_id],
                notes=[f"Captured {checkpoint.file_count} file fingerprints."],
            )
        )
    except SandboxPolicyError as exc:
        escalation_reasons.append(str(exc))
        step_results.append(
            RunStepResult(
                step_id="step_2_readonly_inspection",
                title="Read-only Inspection",
                status="blocked",
                notes=[str(exc)],
            )
        )

    plan_evidence = record_evidence(
        run_id,
        "verification",
        "Sandbox plan and verification gates prepared.",
        passed=True,
        payload={
            "tools_required": spec.tools_required,
            "verification_rules": [rule.rule_id for rule in spec.verification_rules],
            "budgets": spec.budgets.model_dump(mode="json"),
        },
        home=home,
    )
    step_results.append(
        RunStepResult(
            step_id="step_3_sandbox_plan",
            title="Sandbox Plan",
            status="completed",
            evidence_ids=[plan_evidence.evidence_id],
            notes=["Execution remains inside approved workspace and budget policy."],
        )
    )

    implementation_reason = (
        "No concrete implementation task executor is attached yet; controlled implementation "
        "requires a tool plan from milestones beyond the current scaffold."
    )
    escalation_reasons.append(implementation_reason)
    impl_evidence = record_evidence(
        run_id,
        "note",
        "Controlled implementation gate reached.",
        passed=False,
        payload={"reason": implementation_reason},
        home=home,
    )
    step_results.append(
        RunStepResult(
            step_id="step_4_controlled_implementation",
            title="Controlled Implementation",
            status="escalated",
            evidence_ids=[impl_evidence.evidence_id],
            notes=[implementation_reason],
        )
    )

    diff_report = diff_gate(run_id, home=home)
    step_results.append(
        RunStepResult(
            step_id="step_5_verification_and_report",
            title="Verification and Report",
            status="completed" if diff_report.allowed else "blocked",
            evidence_ids=[],
            notes=[diff_report.summary],
        )
    )

    completed = sum(1 for step in step_results if step.status == "completed")
    progress_score = completed / len(step_results)
    status = "escalated" if escalation_reasons else "completed"
    report = SisyphusRunReport(
        run_id=run_id,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        status=status,
        iterations=max(1, max_iterations),
        progress_score=progress_score,
        loop_detected=_detect_loop([step.status for step in step_results]),
        step_results=step_results,
        escalation_reasons=escalation_reasons,
    )
    artifact = store.artifacts_for(run_id).run_dir / "reports" / "sisyphus_report.json"
    report.artifact_paths = [str(artifact)]
    write_private_json(artifact, report.model_dump(mode="json"))
    EventLog(home).append(
        new_trace_event(
            "sisyphus.run.finished",
            run_id=run_id,
            payload={
                "report_id": report.report_id,
                "status": report.status,
                "progress_score": report.progress_score,
                "artifact": str(artifact),
            },
        )
    )
    return report


def _detect_loop(statuses: list[str]) -> bool:
    if len(statuses) < 4:
        return False
    return statuses[-4:] in (["blocked", "completed", "blocked", "completed"], ["completed", "blocked", "completed", "blocked"])
