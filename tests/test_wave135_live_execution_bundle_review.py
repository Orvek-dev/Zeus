from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_bundle_review_runtime import LiveExecutionBundleReviewRuntime
from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleRuntime
from tests.test_wave134_live_execution_bundle import _gateway_result, _mcp_result, _provider_result


def test_live_execution_bundle_review_records_independent_review() -> None:
    bundle = _bundle()

    result = LiveExecutionBundleReviewRuntime().review(
        bundle=bundle,
        reviewer_id="reviewer.wave135",
        producer_id="producer.wave135",
        evidence_ids=("ev-command-wave135", "ev-runtime-wave135"),
        risk_acknowledgements=("loopback_only", "no_production_claim", "cleanup_recorded"),
    )

    assert result.decision == "review_recorded"
    assert result.review_id is not None
    assert result.bundle_id == bundle.bundle_id
    assert result.independent_review is True
    assert result.evidence_count == 2
    assert result.bundle_surface_count == 3
    assert result.production_ready is False
    assert result.live_production_claimed is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_live_execution_bundle_review_blocks_self_review_and_missing_ack() -> None:
    result = LiveExecutionBundleReviewRuntime().review(
        bundle=_bundle(),
        reviewer_id="same.operator",
        producer_id="same.operator",
        evidence_ids=("ev-command-wave135",),
        risk_acknowledgements=("loopback_only",),
    )

    assert result.decision == "blocked"
    assert "independent_reviewer_required" in result.blocked_reasons
    assert "risk_ack:no_production_claim_required" in result.blocked_reasons
    assert "risk_ack:cleanup_recorded_required" in result.blocked_reasons
    assert result.independent_review is False


def test_live_execution_bundle_review_blocks_unsafe_bundle() -> None:
    unsafe_bundle = _bundle().model_copy(update={"no_secret_echo": False})

    result = LiveExecutionBundleReviewRuntime().review(
        bundle=unsafe_bundle,
        reviewer_id="reviewer.wave135",
        producer_id="producer.wave135",
        evidence_ids=("ev-command-wave135", "ev-runtime-wave135"),
        risk_acknowledgements=("loopback_only", "no_production_claim", "cleanup_recorded"),
    )

    assert result.decision == "blocked"
    assert "bundle_secret_echo_detected" in result.blocked_reasons
    assert result.production_ready is False


def test_cli_and_python_library_live_execution_bundle_review() -> None:
    bundle = _bundle()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-execution-bundle-review",
            "--bundle-json",
            bundle.model_dump_json(),
            "--reviewer-id",
            "reviewer.wave135",
            "--producer-id",
            "producer.wave135",
            "--evidence-id",
            "ev-command-wave135",
            "--evidence-id",
            "ev-runtime-wave135",
            "--risk-ack",
            "loopback_only",
            "--risk-ack",
            "no_production_claim",
            "--risk-ack",
            "cleanup_recorded",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "review_recorded"
    assert payload["independent_review"] is True

    library_payload = ZeusAgent().live_execution_bundle_review(
        bundle.to_payload(),
        reviewer_id="reviewer.wave135",
        producer_id="producer.wave135",
        evidence_ids=("ev-command-wave135", "ev-runtime-wave135"),
        risk_acknowledgements=("loopback_only", "no_production_claim", "cleanup_recorded"),
    )
    assert library_payload["decision"] == "review_recorded"
    assert library_payload["production_ready"] is False


def _bundle():
    return LiveExecutionBundleRuntime().summarize(
        provider_result=_provider_result(),
        gateway_result=_gateway_result(),
        mcp_result=_mcp_result(),
        bundle_ref="live-execution-bundle://wave135/review",
    )
