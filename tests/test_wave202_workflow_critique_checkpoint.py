from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.orchestration_runtime import DynamicWorkflowCompiler, WorkflowCompileRequest


def test_workflow_compiler_emits_critique_checkpoint_for_fan_out() -> None:
    request = WorkflowCompileRequest(
        objective="Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
        risk_level="normal",
        evidence_target="mneme.wave202.workflow",
    )

    plan = DynamicWorkflowCompiler().compile(request)

    assert plan.decision == "compiled"
    assert plan.selected_pattern == "fan_out_and_synthesize"
    assert plan.critique_checkpoint.adaptation_decision == "fan_out_and_synthesize"
    assert plan.critique_checkpoint.evidence_target == "mneme.wave202.workflow"
    assert "lean_ulw" in plan.critique_checkpoint.rejected_alternatives
    assert plan.critique_checkpoint.memory_write_performed is False
    assert plan.critique_checkpoint.authority_widened is False
    assert plan.critique_checkpoint.network_opened is False


def test_workflow_compiler_emits_lean_checkpoint_for_small_low_risk_work() -> None:
    request = WorkflowCompileRequest(
        objective="Polish one local documentation typo",
        task_count=1,
        requires_code=False,
        risk_level="low",
        evidence_target="mneme.wave202.lean",
    )

    plan = DynamicWorkflowCompiler().compile(request)

    assert plan.decision == "compiled"
    assert plan.selected_pattern == "lean_ulw"
    assert plan.why_not_decision == "lean_down"
    assert plan.critique_checkpoint.starting_pattern == "lean_ulw"
    assert plan.critique_checkpoint.adaptation_decision == "lean_ulw"
    assert "fan_out_and_synthesize" in plan.critique_checkpoint.rejected_alternatives
    assert "minimize orchestration" in plan.critique_checkpoint.critique_question


def test_workflow_cockpit_surfaces_adaptive_critique_checkpoint_cli() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "workflow", "--workflow-id", "adaptive", "--json"],
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    checkpoint = payload["selected_workflow"]["critique_checkpoint"]
    assert checkpoint["adaptation_decision"] == "fan_out_and_synthesize"
    assert checkpoint["memory_write_performed"] is False
    assert checkpoint["authority_widened"] is False
    assert payload["network_opened"] is False
