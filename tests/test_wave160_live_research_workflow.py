from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def test_live_research_workflow_compiles_default_source_plan_without_network() -> None:
    result = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave160.objective",
    )
    payload = result.to_payload()
    source_states = {source["source_id"]: source["state"] for source in payload["sources"]}

    assert payload["decision"] == "workflow_planned"
    assert payload["source_count"] == 3
    assert payload["ready_source_count"] == 1
    assert payload["endpoint_required_count"] == 2
    assert source_states == {"github": "ready_for_policy", "web": "endpoint_required", "community": "endpoint_required"}
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_live_research_workflow_endpoint_overrides_prepare_all_sources() -> None:
    result = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave160.objective",
        endpoint_overrides={
            "web": "https://search.example.dev/query",
            "community": "https://community.example.dev/search",
        },
    )

    assert result.decision == "workflow_planned"
    assert result.ready_source_count == 3
    assert result.endpoint_required_count == 0
    assert all(source.endpoint_bound for source in result.sources)
    assert result.network_opened is False


def test_live_research_workflow_blocks_secret_endpoint_override() -> None:
    result = LiveResearchWorkflowRuntime().compile_workflow(
        query="parallel coding workflow",
        objective_id="wave160.objective",
        endpoint_overrides={"web": "https://search.example.dev/query?token=ghp_" + "wave160"},
    )
    serialized = json.dumps(result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_workflow_endpoint_contains_secret" in result.blocked_reasons
    assert "ghp_" + "wave160" not in serialized
    assert result.no_secret_echo is True


def test_live_research_workflow_cli_and_library_surface_match() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow",
            "--query",
            "parallel coding workflow",
            "--objective-id",
            "wave160.objective",
            "--endpoint",
            "web=https://search.example.dev/query",
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
    library_payload = ZeusAgent().live_research_workflow(
        query="parallel coding workflow",
        objective_id="wave160.objective",
        endpoint_overrides={"web": "https://search.example.dev/query"},
    )
    assert cli_payload == library_payload
