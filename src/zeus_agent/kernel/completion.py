from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .contracts import GoalContract
from .evidence import EvidenceStatus, MnemeEvidenceRecord


class AcceptanceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["complete", "blocked"]
    verified_criteria: list[str]
    missing_criteria: list[str]


class CompletionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[
        "complete",
        "blocked_missing_evidence",
        "blocked_policy",
        "failed_runtime",
    ]
    verified_criteria: list[str]
    missing_criteria: list[str]
    blocked_criteria: list[str]
    failed_criteria: list[str]


def map_acceptance_evidence(
    contract: GoalContract,
    records: list[MnemeEvidenceRecord],
) -> AcceptanceEvidence:
    verified = []
    missing = []
    for criterion in contract.acceptance_criteria:
        matching_pass = [
            record
            for record in records
            if record.criterion_id == criterion and record.status == EvidenceStatus.PASS
        ]
        if matching_pass:
            verified.append(criterion)
        else:
            missing.append(criterion)
    status: Literal["complete", "blocked"] = "complete" if not missing else "blocked"
    return AcceptanceEvidence(
        status=status,
        verified_criteria=verified,
        missing_criteria=missing,
    )


def summarize_completion(
    contract: GoalContract,
    records: list[MnemeEvidenceRecord],
    final_message: str | None = None,
) -> CompletionSummary:
    del final_message
    verified = []
    missing = []
    blocked = []
    failed = []
    for criterion in contract.acceptance_criteria:
        criterion_records = [
            record
            for record in records
            if record.criterion_id == criterion
            and record.goal_contract_id == contract.goal_contract_id
        ]
        failed_records = [
            record
            for record in criterion_records
            if record.status == EvidenceStatus.FAIL
        ]
        blocked_records = [
            record
            for record in criterion_records
            if record.status == EvidenceStatus.BLOCKED
        ]
        passing_records = [
            record
            for record in criterion_records
            if record.status == EvidenceStatus.PASS
        ]
        if failed_records:
            failed.append(criterion)
        elif blocked_records:
            blocked.append(criterion)
        elif passing_records:
            verified.append(criterion)
        else:
            missing.append(criterion)

    status: Literal[
        "complete",
        "blocked_missing_evidence",
        "blocked_policy",
        "failed_runtime",
    ]
    if failed:
        status = "failed_runtime"
    elif blocked:
        status = "blocked_policy"
    elif missing:
        status = "blocked_missing_evidence"
    else:
        status = "complete"
    return CompletionSummary(
        status=status,
        verified_criteria=verified,
        missing_criteria=missing,
        blocked_criteria=blocked,
        failed_criteria=failed,
    )
