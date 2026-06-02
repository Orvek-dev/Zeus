from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WorkflowStatus = Literal["pending", "retry_pending", "succeeded", "failed"]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_seconds: int

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts_must_be_positive")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds_must_be_non_negative")


@dataclass(frozen=True)
class CompensationMetadata:
    command: str
    target: str
    executed: bool = False


@dataclass(frozen=True)
class WorkflowJob:
    principal_id: str
    session_id: str
    job_id: str
    idempotency_key: str
    status: WorkflowStatus
    attempt: int
    retry_policy: RetryPolicy
    compensation: CompensationMetadata


class WorkflowPlanner:
    def plan(
        self,
        *,
        principal_id: str,
        session_id: str,
        job_id: str,
        idempotency_key: str,
        retry_policy: RetryPolicy,
        compensation: CompensationMetadata,
    ) -> WorkflowJob:
        return WorkflowJob(
            principal_id=principal_id,
            session_id=session_id,
            job_id=job_id,
            idempotency_key=idempotency_key,
            status="pending",
            attempt=0,
            retry_policy=retry_policy,
            compensation=compensation,
        )

    def next_retry(self, current: WorkflowJob) -> WorkflowJob:
        next_attempt = current.attempt + 1
        if next_attempt >= current.retry_policy.max_attempts:
            return WorkflowJob(
                principal_id=current.principal_id,
                session_id=current.session_id,
                job_id=current.job_id,
                idempotency_key=current.idempotency_key,
                status="failed",
                attempt=next_attempt,
                retry_policy=current.retry_policy,
                compensation=current.compensation,
            )
        return WorkflowJob(
            principal_id=current.principal_id,
            session_id=current.session_id,
            job_id=current.job_id,
            idempotency_key=current.idempotency_key,
            status="retry_pending",
            attempt=next_attempt,
            retry_policy=current.retry_policy,
            compensation=current.compensation,
        )
