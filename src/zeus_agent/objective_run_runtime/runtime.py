from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, Optional, Sequence

from pydantic import ValidationError

from zeus_agent.kernel.completion import summarize_completion
from zeus_agent.kernel.contracts import GoalContract
from zeus_agent.kernel.evidence import MnemeEvidenceRecord
from zeus_agent.objective_runtime import ObjectiveCompiler, ZeusObjectiveContract
from zeus_agent.objective_run_runtime.models import (
    ObjectiveRun,
    ObjectiveRunResult,
    ObjectiveRunStatus,
    ObjectiveRunStoreSnapshot,
)


class ObjectiveRunStoreError(ValueError):
    pass


class ObjectiveRunStore:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.path = home / "objective-runs.json"

    def upsert(self, run: ObjectiveRun) -> ObjectiveRun:
        snapshot = self._load()
        retained = tuple(item for item in snapshot.runs if item.run_id != run.run_id)
        self._save(ObjectiveRunStoreSnapshot(runs=(*retained, run)))
        return run

    def get(self, run_id: str) -> Optional[ObjectiveRun]:
        safe_run_id = run_id.strip()
        if safe_run_id == "":
            return None
        snapshot = self._load()
        for run in snapshot.runs:
            if run.run_id == safe_run_id:
                return run
        return None

    def _load(self) -> ObjectiveRunStoreSnapshot:
        if not self.path.exists():
            return ObjectiveRunStoreSnapshot()
        try:
            return ObjectiveRunStoreSnapshot.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (ValidationError, ValueError) as exc:
            raise ObjectiveRunStoreError("objective_run_store_invalid") from exc

    def _save(self, snapshot: ObjectiveRunStoreSnapshot) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, indent=2),
            encoding="utf-8",
        )


class ObjectiveRunRuntime:
    def __init__(self, store: ObjectiveRunStore) -> None:
        self.store = store
        self.compiler = ObjectiveCompiler()

    def start(
        self,
        *,
        objective: str,
        session_id: str,
        principal_id: str,
        acceptance_criteria: Sequence[str] | None = None,
        constraints: Sequence[str] | None = None,
    ) -> ObjectiveRunResult:
        contract = self.compiler.compile(objective, constraints=constraints)
        criteria = _acceptance_criteria(contract, acceptance_criteria)
        goal_contract = GoalContract(
            goal_contract_id=contract.objective_id,
            raw_user_request=contract.raw_user_request,
            normalized_goal=contract.normalized_objective,
            deliverables=contract.deliverables or ("Blocked objective contract",),
            acceptance_criteria=criteria,
        )
        completion = summarize_completion(goal_contract, [])
        status = _initial_status(contract)
        run = ObjectiveRun(
            objective_id=contract.objective_id,
            run_id=_run_id(contract.objective_id, session_id, principal_id),
            session_id=session_id,
            principal_id=principal_id,
            status=status,
            objective_contract=contract,
            goal_contract=goal_contract,
            current_plan=_current_plan(contract, criteria),
            completion_summary=completion,
            blocked_reasons=tuple(contract.block_reasons),
        )
        self.store.upsert(run)
        return _result(decision="started", run=run)

    def status(self, run_id: str) -> ObjectiveRunResult:
        run = self.store.get(run_id)
        if run is None:
            return _result(decision="blocked", blocked_reasons=("objective_run_not_found",))
        return _result(decision="reported", run=run)

    def export(self, run_id: str) -> ObjectiveRunResult:
        run = self.store.get(run_id)
        if run is None:
            return _result(decision="blocked", blocked_reasons=("objective_run_not_found",))
        return _result(decision="exported", run=run)

    def record_evidence(self, *, run_id: str, evidence: MnemeEvidenceRecord) -> ObjectiveRunResult:
        run = self.store.get(run_id)
        if run is None:
            return _result(decision="blocked", blocked_reasons=("objective_run_not_found",))
        reasons = _evidence_reasons(run, evidence)
        if reasons:
            return _result(decision="blocked", run=run, blocked_reasons=reasons)
        records = (*run.evidence_records, evidence)
        completion = summarize_completion(run.goal_contract, list(records))
        updated = run.model_copy(
            update={
                "status": _status_from_completion(completion.status),
                "evidence_records": records,
                "completion_summary": completion,
            }
        )
        self.store.upsert(updated)
        return _result(decision="updated", run=updated)


def _acceptance_criteria(
    contract: ZeusObjectiveContract,
    acceptance_criteria: Sequence[str] | None,
) -> tuple[str, ...]:
    cleaned = tuple(item.strip() for item in acceptance_criteria or () if item.strip())
    if cleaned:
        return cleaned
    return tuple(obligation.evidence_target for obligation in contract.verification_obligations)


def _initial_status(contract: ZeusObjectiveContract) -> ObjectiveRunStatus:
    if contract.blocked:
        return "blocked"
    return "planned"


def _status_from_completion(status: str) -> ObjectiveRunStatus:
    if status == "complete":
        return "complete"
    if status == "failed_runtime":
        return "failed"
    return "verifying"


def _current_plan(contract: ZeusObjectiveContract, criteria: tuple[str, ...]) -> tuple[str, ...]:
    if contract.blocked:
        return ("repair_blocked_objective_contract",)
    return (
        "compile_objective_contract",
        "resolve_authority_and_runtime_leases",
        "collect_evidence_for_{0}_criteria".format(len(criteria)),
        "arbitrate_completion_from_evidence",
    )


def _run_id(objective_id: str, session_id: str, principal_id: str) -> str:
    payload = json.dumps(
        {
            "objective_id": objective_id,
            "principal_id": principal_id.strip(),
            "session_id": session_id.strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "run-{0}".format(hashlib.sha256(payload).hexdigest()[:16])


def _evidence_reasons(run: ObjectiveRun, evidence: MnemeEvidenceRecord) -> tuple[str, ...]:
    reasons: list[str] = []
    if evidence.run_id != run.run_id:
        reasons.append("evidence_run_mismatch")
    if evidence.goal_contract_id != run.goal_contract.goal_contract_id:
        reasons.append("evidence_goal_contract_mismatch")
    if evidence.criterion_id not in run.goal_contract.acceptance_criteria:
        reasons.append("evidence_criterion_not_in_contract")
    return tuple(dict.fromkeys(reasons))


def _result(
    *,
    decision: Literal["started", "reported", "exported", "updated", "blocked"],
    run: Optional[ObjectiveRun] = None,
    blocked_reasons: tuple[str, ...] = (),
) -> ObjectiveRunResult:
    return ObjectiveRunResult(
        decision=decision,
        run=run,
        blocked_reasons=blocked_reasons,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
