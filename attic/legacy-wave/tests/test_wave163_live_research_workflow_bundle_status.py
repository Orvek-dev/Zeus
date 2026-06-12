from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_workflow_bundle_status_marks_ready_bundle_without_network() -> None:
    bundle = _bundle(
        endpoint_overrides={
            "web": "https://search.example.dev/query",
            "community": "https://community.example.dev/search",
        },
    )

    result = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    payload = result.to_payload()

    assert payload["decision"] == "bundle_ready"
    assert payload["bundle_id"] == bundle.bundle_id
    assert payload["planned_source_count"] == 3
    assert payload["endpoint_required_count"] == 0
    assert payload["blocked_source_count"] == 0
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_workflow_bundle_status_keeps_endpoint_gaps_visible() -> None:
    bundle = _bundle(endpoint_overrides={"web": "https://search.example.dev/query"})

    result = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)

    assert result.decision == "endpoint_gaps"
    assert result.source_plan_count == 3
    assert result.planned_source_count == 2
    assert result.endpoint_required_count == 1
    assert "live_research_workflow_bundle_endpoint_gaps" in result.blocked_reasons
    assert any("live-research-workflow" in command for command in result.recommended_next_commands)


def test_workflow_bundle_status_blocks_blocked_bundle_without_echoing_secret() -> None:
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave163.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave163"},
    )
    bundle = LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave163/blocked",
    )

    result = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_workflow_bundle_blocked" in result.blocked_reasons
    assert "ghp_" + "wave163" not in serialized
    assert result.no_secret_echo is True


def test_workflow_bundle_status_cli_and_library_surface_match() -> None:
    bundle = _bundle(endpoint_overrides={"web": "https://search.example.dev/query"})
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-bundle-status",
            "--bundle-json",
            bundle.model_dump_json(),
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
    library_payload = ZeusAgent().live_research_workflow_bundle_status(bundle=bundle.to_payload())
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "endpoint_gaps"


def _bundle(*, endpoint_overrides: dict[str, str]):
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave163.objective",
        endpoint_overrides=endpoint_overrides,
    )
    return LiveResearchWorkflowBundleRuntime().build(
        workflow=workflow,
        bundle_ref="research-bundle://wave163",
    )
