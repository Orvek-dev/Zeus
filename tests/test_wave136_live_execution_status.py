from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_bundle_review_runtime import LiveExecutionBundleReviewRuntime
from zeus_agent.live_execution_status_runtime import LiveExecutionStatusRuntime
from tests.test_wave135_live_execution_bundle_review import _bundle


def test_live_execution_status_reports_pending_review_for_bundle() -> None:
    bundle = _bundle()

    result = LiveExecutionStatusRuntime().build(bundle=bundle, review=None)

    assert result.decision == "pending_review"
    assert result.bundle_id == bundle.bundle_id
    assert result.review_recorded is False
    assert result.bundle_surface_count == 3
    assert result.production_ready is False
    assert result.live_production_claimed is False
    assert "zeus live-execution-bundle-review --json" in result.recommended_next_commands


def test_live_execution_status_reports_reviewed_bundle() -> None:
    bundle = _bundle()
    review = _review(bundle)

    result = LiveExecutionStatusRuntime().build(bundle=bundle, review=review)

    assert result.decision == "reviewed"
    assert result.review_id == review.review_id
    assert result.review_recorded is True
    assert result.independent_review is True
    assert result.evidence_count == 2
    assert result.production_ready is False
    assert result.network_opened is False
    assert result.bundle_network_opened is True


def test_live_execution_status_blocks_mismatched_review() -> None:
    bundle = _bundle()
    review = _review(bundle).model_copy(update={"bundle_id": "wrong-bundle"})

    result = LiveExecutionStatusRuntime().build(bundle=bundle, review=review)

    assert result.decision == "blocked"
    assert "review_bundle_mismatch" in result.blocked_reasons
    assert result.production_ready is False


def test_cli_and_python_library_live_execution_status() -> None:
    bundle = _bundle()
    review = _review(bundle)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-execution-status",
            "--bundle-json",
            bundle.model_dump_json(),
            "--review-json",
            review.model_dump_json(),
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "reviewed"
    assert payload["production_ready"] is False

    library_payload = ZeusAgent().live_execution_status(
        bundle.to_payload(),
        review.to_payload(),
    )
    assert library_payload["decision"] == "reviewed"
    assert library_payload["review_recorded"] is True


def _review(bundle):
    return LiveExecutionBundleReviewRuntime().review(
        bundle=bundle,
        reviewer_id="reviewer.wave136",
        producer_id="producer.wave136",
        evidence_ids=("ev-command-wave136", "ev-runtime-wave136"),
        risk_acknowledgements=("loopback_only", "no_production_claim", "cleanup_recorded"),
    )
