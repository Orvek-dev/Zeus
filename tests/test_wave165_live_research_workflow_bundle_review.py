from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_workflow_bundle_review_requires_endpoint_configuration_for_gaps() -> None:
    bundle, status = _bundle_and_status(endpoint_overrides={"web": "https://search.example.dev/query"})

    result = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave165/gaps",
    )

    assert result.decision == "operator_input_required"
    assert result.endpoint_required_count == 1
    assert result.external_review_required_count == 0
    assert "live_research_workflow_bundle_endpoint_gaps" in result.blocked_reasons
    assert any("configure missing endpoints" in action for action in result.required_operator_actions)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_workflow_bundle_review_requires_external_review_for_non_loopback_sources() -> None:
    bundle, status = _bundle_and_status(
        endpoint_overrides={
            "web": "https://search.example.dev/query",
            "community": "https://community.example.dev/search",
        },
    )

    result = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave165/external",
    )

    assert status.decision == "bundle_ready"
    assert result.decision == "operator_input_required"
    assert result.endpoint_required_count == 0
    assert result.external_review_required_count == 3
    assert "live_research_external_review_required" in result.blocked_reasons
    assert any("production fetcher" in action for action in result.required_operator_actions)
    assert result.credential_material_accessed is False


def test_workflow_bundle_review_blocks_blocked_status_without_echoing_secret() -> None:
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave165.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave165"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave165/blocked",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)

    result = LiveResearchWorkflowBundleReviewRuntime().review(
        bundle=bundle,
        status=status,
        review_ref="review://wave165/blocked",
    )
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert "ghp_" + "wave165" not in serialized
    assert result.no_secret_echo is True


def test_workflow_bundle_review_cli_and_library_surface_match() -> None:
    bundle, status = _bundle_and_status(endpoint_overrides={"web": "https://search.example.dev/query"})
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-bundle-review",
            "--bundle-json",
            bundle.model_dump_json(),
            "--status-json",
            status.model_dump_json(),
            "--review-ref",
            "review://wave165/cli",
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    library_payload = ZeusAgent().live_research_workflow_bundle_review(
        bundle=bundle.to_payload(),
        status=status.to_payload(),
        review_ref="review://wave165/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "operator_input_required"


def _bundle_and_status(*, endpoint_overrides: dict[str, str]):
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave165.objective",
        endpoint_overrides=endpoint_overrides,
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave165",
    )
    status = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    return bundle, status
