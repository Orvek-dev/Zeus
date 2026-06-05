from __future__ import annotations

import json

from zeus_agent.verification_runtime import ReviewBindingRequest, bind_review


def test_review_binding_approves_independent_review_with_evidence() -> None:
    # Given: an independent reviewer covers changed paths and evidence ids.
    request = ReviewBindingRequest(
        change_set_id="wave30.review.slice",
        producer_id="main-codex",
        reviewer_id="reviewer.local",
        verdict="approved",
        reviewed_paths=("src/zeus_agent/workflow_runtime/cron.py",),
        evidence_ids=("ev-wave30-tests",),
    )

    # When: the review is bound to the wave checkpoint.
    result = bind_review(request)

    # Then: the checkpoint can use the binding as independent review evidence.
    assert result.decision == "approved"
    assert result.reason == "independent_review_bound"
    assert result.review_required is False
    assert result.no_secret_echo is True


def test_review_binding_blocks_producer_self_review_missing_evidence_and_secret_echo() -> None:
    # Given: a producer tries to approve its own change and includes secret-like text.
    request = ReviewBindingRequest(
        change_set_id="wave30.review.self",
        producer_id="main-codex",
        reviewer_id="main-codex",
        verdict="approved",
        reviewed_paths=(),
        evidence_ids=(),
        findings=("checked token=sk-wave30-secret",),
    )

    # When: the review is bound.
    result = bind_review(request)
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)

    # Then: Zeus blocks the review and redacts the finding.
    assert result.decision == "blocked"
    assert "producer_self_review" in result.blocked_reasons
    assert "missing_reviewed_paths" in result.blocked_reasons
    assert "missing_evidence_ids" in result.blocked_reasons
    assert "sk-wave30-secret" not in serialized
    assert result.no_secret_echo is True
