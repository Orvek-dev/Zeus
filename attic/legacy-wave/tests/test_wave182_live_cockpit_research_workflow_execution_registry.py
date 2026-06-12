from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_execution_registry_runtime import (
    LiveResearchWorkflowExecutionRegistryRuntime,
)
from tests.test_wave180_live_research_workflow_execution_registry import _status


def test_live_cockpit_reports_research_workflow_execution_registry(tmp_path: Path) -> None:
    registry = _listed_registry(tmp_path)

    result = LiveCockpitRuntime().build(research_workflow_execution_registry=registry)

    assert result.decision == "report"
    assert result.research_workflow_execution_registry == registry
    assert result.research_workflow_execution_registry_decision == "listed"
    assert result.research_workflow_execution_registry_ready is True
    assert result.research_workflow_execution_registry_record_count == 1
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "zeus live-research-workflow-execution-records --json" in result.recommended_next_commands


def test_live_cockpit_blocks_blocked_research_workflow_execution_registry(tmp_path: Path) -> None:
    unsafe = _status().model_copy(update={"no_secret_echo": False})
    registry = LiveResearchWorkflowExecutionRegistryRuntime(tmp_path).record(
        status=unsafe,
        record_ref="research-workflow-execution-record://wave182/unsafe",
    )

    result = LiveCockpitRuntime().build(research_workflow_execution_registry=registry)

    assert result.decision == "blocked"
    assert (
        "research-workflow-execution-registry:status_secret_echo_detected"
    ) in result.blocked_reasons
    assert result.research_workflow_execution_registry_ready is False


def test_live_cockpit_execution_registry_cli_and_library_surface_match(tmp_path: Path) -> None:
    registry = _listed_registry(tmp_path)
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live",
            "--research-workflow-execution-registry-json",
            registry.model_dump_json(),
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
    library_payload = ZeusAgent().live_status(
        research_workflow_execution_registry=registry.to_payload(),
    )
    assert cli_payload == library_payload
    assert cli_payload["research_workflow_execution_registry_decision"] == "listed"
    assert cli_payload["research_workflow_execution_registry_record_count"] == 1


def _listed_registry(home: Path):
    runtime = LiveResearchWorkflowExecutionRegistryRuntime(home)
    runtime.record(
        status=_status(),
        record_ref="research-workflow-execution-record://wave182/listed",
    )
    return runtime.list()
