from __future__ import annotations

import json

import pytest

from zeus_agent.gateway_runtime.drafts import CronDraft, GatewayDraft, draft_cron_command, draft_gateway_command
from zeus_agent.security.credentials import (
    CredentialScope,
    CredentialScopeUnsafeError,
    credential_report,
    redact_secret_like,
)
from zeus_agent.workflow_runtime.jobs import (
    CompensationMetadata,
    RetryPolicy,
    WorkflowJob,
    WorkflowPlanner,
)


def test_credential_scope_accepts_non_secret_labels_and_report_never_leaks_values() -> None:
    # Given: credential labels that are policy-safe and no secret material.
    labels = ["external.openai.readonly", "external.anthropic.prod"]

    # When: scopes are parsed and summarized in a credential report.
    scopes = [CredentialScope.parse(label) for label in labels]
    report = credential_report(scopes)
    dumped = json.dumps(report, sort_keys=True)

    # Then: only credential_scope labels appear and no raw secret values exist.
    assert [scope.label for scope in scopes] == labels
    assert report == {"credential_scopes": labels, "count": 2}
    assert "sk-" not in dumped


def test_credential_scope_rejects_secret_like_values_without_echoing_secret() -> None:
    # Given: a secret-like value mistakenly passed as credential scope.
    raw_secret = "sk-test-raw-secret-value"

    # When: parsing the scope fails closed.
    with pytest.raises(CredentialScopeUnsafeError) as captured:
        CredentialScope.parse(raw_secret)

    # Then: the error payload contains redacted metadata only.
    payload = captured.value.payload
    dumped = json.dumps(payload, sort_keys=True)
    assert payload["reason"] == "secret_like_credential_scope"
    assert payload["redacted"] == "sk-...redacted"
    assert raw_secret not in dumped
    assert payload["input"] != raw_secret


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sk-live-123", "sk-...redacted"),
        ("ghp_TEST_FIXTURE", "[redacted-secret]"),
        ("xoxb-test-fixture", "[redacted-secret]"),
        ("Bearer abcdefghijklmnopqrstuvwxyz", "[redacted-secret]"),
        ("api_key=abcdef", "[redacted-secret]"),
        ("token=secret", "[redacted-secret]"),
        ("external.openai.readonly", "external.openai.readonly"),
    ],
)
def test_redaction_helper_never_returns_raw_secret_like_values(value: str, expected: str) -> None:
    # Given: values that may or may not be secret-like.
    # When: the helper redacts secret-like values for logs and dumps.
    # Then: secret-like values are masked while safe labels pass through.
    assert redact_secret_like(value) == expected


def test_workflow_planner_creates_pending_job_with_principal_and_retry_compensation_metadata() -> None:
    # Given: deterministic workflow inputs and retry/compensation metadata.
    retry_policy = RetryPolicy(max_attempts=3, backoff_seconds=30)
    compensation = CompensationMetadata(command="revert-cache", target="orders-cache")
    planner = WorkflowPlanner()

    # When: a new pending workflow job is planned.
    job = planner.plan(
        principal_id="principal-wave4",
        session_id="session-wave4",
        job_id="job-wave4-001",
        idempotency_key="idem-wave4-001",
        retry_policy=retry_policy,
        compensation=compensation,
    )

    # Then: required runtime fields exist and compensation remains data-only metadata.
    assert isinstance(job, WorkflowJob)
    assert job.principal_id == "principal-wave4"
    assert job.session_id == "session-wave4"
    assert job.job_id == "job-wave4-001"
    assert job.idempotency_key == "idem-wave4-001"
    assert job.status == "pending"
    assert job.attempt == 0
    assert job.retry_policy == retry_policy
    assert job.compensation == compensation
    assert job.compensation.executed is False
    assert "execute" not in dir(job.compensation)


def test_workflow_retry_creates_next_attempt_deterministically_with_same_idempotency_key() -> None:
    # Given: a pending workflow job with deterministic identity.
    planner = WorkflowPlanner()
    original = planner.plan(
        principal_id="principal-wave4",
        session_id="session-wave4",
        job_id="job-wave4-002",
        idempotency_key="idem-wave4-002",
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=5),
        compensation=CompensationMetadata(command="rollback-state", target="state-store"),
    )

    # When: planner computes the next retry attempt.
    retry = planner.next_retry(original)

    # Then: attempt increments while idempotency key and identifiers remain stable.
    assert retry.principal_id == original.principal_id
    assert retry.session_id == original.session_id
    assert retry.job_id == original.job_id
    assert retry.idempotency_key == original.idempotency_key
    assert retry.status == "retry_pending"
    assert retry.attempt == 1
    assert retry.retry_policy == original.retry_policy
    assert retry.compensation == original.compensation


def test_gateway_and_cron_drafts_are_draft_only_no_side_effects_and_redact_secrets() -> None:
    # Given: gateway and cron commands containing secret-like fragments.
    gateway_command = "send --api-key sk-live-secret --to queue://dispatch"
    cron_command = "install --token=secret --schedule '*/5 * * * *'"

    # When: draft envelopes are created for runtime planning.
    gateway = draft_gateway_command(command=gateway_command, target="gateway.dispatch")
    cron = draft_cron_command(command=cron_command, target="cron.scheduler")

    # Then: both surfaces are explicitly draft-only and secret-like fragments are redacted.
    assert isinstance(gateway, GatewayDraft)
    assert gateway.draft_only is True
    assert gateway.side_effects is False
    assert gateway.status == "drafted"
    assert "sk-live-secret" not in gateway.command
    assert gateway.command == "[redacted-secret]"

    assert isinstance(cron, CronDraft)
    assert cron.draft_only is True
    assert cron.side_effects is False
    assert cron.status == "drafted"
    assert "token=secret" not in cron.command
    assert cron.command == "[redacted-secret]"
