from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_workflow_bundle_plans_ready_sources_and_keeps_endpoint_gaps() -> None:
    workflow = _workflow()

    result = LiveResearchWorkflowBundleRuntime().build(workflow=workflow, bundle_ref="research-bundle://wave162")
    payload = result.to_payload()
    source_states = {source["source_id"]: source["state"] for source in payload["source_plans"]}

    assert payload["decision"] == "bundle_planned"
    assert payload["source_plan_count"] == 3
    assert payload["planned_source_count"] == 2
    assert payload["endpoint_required_count"] == 1
    assert source_states == {"github": "planned", "web": "planned", "community": "endpoint_required"}
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_workflow_bundle_blocks_blocked_workflow_without_planning_sources() -> None:
    workflow = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave162.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave162"},
    )

    result = LiveResearchWorkflowBundleRuntime().build(workflow=workflow, bundle_ref="research-bundle://blocked")
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_workflow_not_planned" in result.blocked_reasons
    assert result.source_plan_count == 0
    assert "ghp_" + "wave162" not in serialized
    assert result.no_secret_echo is True


def test_workflow_bundle_cli_and_library_surface_match() -> None:
    workflow = _workflow()
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-bundle",
            "--workflow-json",
            workflow.model_dump_json(),
            "--bundle-ref",
            "research-bundle://wave162/cli",
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
    library_payload = ZeusAgent().live_research_workflow_bundle(
        workflow=workflow.to_payload(),
        bundle_ref="research-bundle://wave162/cli",
    )
    assert cli_payload == library_payload
    assert cli_payload["planned_source_count"] == 2


def _workflow():
    return LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave162.objective",
        endpoint_overrides={"web": "https://search.example.dev/query"},
    )
