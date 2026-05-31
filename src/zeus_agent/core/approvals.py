"""Human approval state transitions."""

from __future__ import annotations

from pathlib import Path

from zeus_agent.schemas.approval import ApprovalRecord
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.security.redaction import redact_text
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.run_store import RunStore


def approve_run(
    run_id: str,
    *,
    approval_text: str = "",
    actor: str = "user",
    home: Path | None = None,
) -> tuple[ApprovalRecord, dict[str, object]]:
    store = RunStore(home)
    contract = store.load_goal_contract(run_id)
    spec = store.load_execution_spec(run_id)
    cleaned = redact_text(approval_text)
    contract.approval_state = "approved"
    spec.status = "approved"
    spec.execution_mode = "sandbox_after_approval"
    spec.sandbox.isolation = "process"
    record = ApprovalRecord(
        run_id=run_id,
        goal_contract_id=contract.goal_id,
        actor=actor,
        decision="approved",
        approval_text=cleaned.value,
        sensitive_input_redacted=cleaned.redacted,
        redaction_findings=list(cleaned.findings),
    )
    store.update_goal_contract(contract, run_id)
    store.update_execution_spec(spec)
    store.append_approval(record)
    EventLog(home).append(
        new_trace_event(
            "approval.approved",
            run_id=run_id,
            actor="user",
            payload={"approval_id": record.approval_id, "actor": actor},
        )
    )
    return record, run_status(run_id, home=home)


def reject_run(
    run_id: str,
    *,
    reason: str = "",
    actor: str = "user",
    home: Path | None = None,
) -> tuple[ApprovalRecord, dict[str, object]]:
    store = RunStore(home)
    contract = store.load_goal_contract(run_id)
    spec = store.load_execution_spec(run_id)
    cleaned = redact_text(reason)
    contract.approval_state = "rejected"
    spec.status = "rejected"
    record = ApprovalRecord(
        run_id=run_id,
        goal_contract_id=contract.goal_id,
        actor=actor,
        decision="rejected",
        reason=cleaned.value,
        sensitive_input_redacted=cleaned.redacted,
        redaction_findings=list(cleaned.findings),
    )
    store.update_goal_contract(contract, run_id)
    store.update_execution_spec(spec)
    store.append_approval(record)
    EventLog(home).append(
        new_trace_event(
            "approval.rejected",
            run_id=run_id,
            actor="user",
            payload={"approval_id": record.approval_id, "actor": actor},
        )
    )
    return record, run_status(run_id, home=home)


def run_status(run_id: str, *, home: Path | None = None) -> dict[str, object]:
    store = RunStore(home)
    contract = store.load_goal_contract(run_id)
    spec = store.load_execution_spec(run_id)
    artifacts = store.artifacts_for(run_id)
    approvals = []
    if artifacts.approvals_path.exists():
        import json

        approvals = [
            json.loads(line)
            for line in artifacts.approvals_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return {
        "run_id": run_id,
        "goal_id": contract.goal_id,
        "approval_state": contract.approval_state,
        "execution_status": spec.status,
        "execution_mode": spec.execution_mode,
        "risk_level": contract.risk_level,
        "normalized_goal": contract.normalized_goal,
        "approval_count": len(approvals),
        "artifacts": artifacts.as_dict(),
    }
