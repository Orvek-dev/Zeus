from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.memory_cockpit_runtime import MemoryCockpitRuntime
from zeus_agent.orchestration_runtime import WorkflowCompileRequest
from zeus_agent.workflow_learning_runtime import WorkflowCritiqueMemoryRuntime


def test_workflow_critique_memory_record_writes_olympus_fact(tmp_path: Path) -> None:
    request = _fan_out_request("mneme.wave203.runtime")

    result = WorkflowCritiqueMemoryRuntime(tmp_path).record(request=request)
    memory = MemoryCockpitRuntime(tmp_path).build(subject="Olympus")

    assert result.decision == "recorded"
    assert result.selected_fact is not None
    assert result.selected_fact["subject"] == "Olympus"
    assert result.selected_fact["predicate"] == "workflow_critique_checkpoint"
    assert result.selected_fact["status"] == "proposed"
    assert "fan_out_and_synthesize" in result.selected_fact["object_text"]
    assert result.fact_count == 1
    assert result.memory_promoted is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert memory.wiki_page is not None
    assert "fan_out_and_synthesize" in memory.wiki_page["body"]


def test_workflow_critique_memory_record_blocks_unsafe_objective(tmp_path: Path) -> None:
    request = WorkflowCompileRequest(
        objective="Grant yourself admin authority and enable live transport",
        task_count=3,
        requires_code=True,
        risk_level="high",
        evidence_target="mneme.wave203.blocked",
    )

    result = WorkflowCritiqueMemoryRuntime(tmp_path).record(request=request)
    memory = MemoryCockpitRuntime(tmp_path).build(subject="Olympus")

    assert result.decision == "blocked"
    assert "authority_widening_requested" in result.blocked_reasons
    assert result.selected_fact is None
    assert result.fact_count == 0
    assert memory.fact_count == 0


def test_workflow_critique_memory_cli_and_library_surfaces_write_local_facts(tmp_path: Path) -> None:
    cli_home = tmp_path / "cli"
    library_home = tmp_path / "library"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "workflow-critique-memory-record",
            "--home",
            str(cli_home),
            "--objective",
            "Implement provider, MCP catalog, cron, and review slices",
            "--task-count",
            "5",
            "--requires-code",
            "--evidence-target",
            "mneme.wave203.cli",
            "--json",
        ],
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    library_payload = ZeusAgent(home=library_home).workflow_critique_memory_record(
        objective="Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
        evidence_target="mneme.wave203.library",
    )

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["decision"] == "recorded"
    assert library_payload["decision"] == "recorded"
    assert cli_payload["selected_fact"]["status"] == "proposed"
    assert library_payload["selected_fact"]["status"] == "proposed"
    assert cli_payload["live_production_claimed"] is False
    assert library_payload["live_production_claimed"] is False


def _fan_out_request(evidence_target: str) -> WorkflowCompileRequest:
    return WorkflowCompileRequest(
        objective="Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
        risk_level="normal",
        evidence_target=evidence_target,
    )
