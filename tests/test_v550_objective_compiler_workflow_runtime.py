from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.objective_compiler_ux_runtime import build_objective_compiler_workflow
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v550_release_gate_reports_objective_compiler_workflow_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v5.5.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v5.5.0"
    assert payload["release_stage"] == "objective_compiler_dynamic_workflow"
    assert payload["objective_compiler_ux_available"] is True
    assert payload["dynamic_workflow_runtime_available"] is True
    assert payload["workflow_dag_available"] is True
    assert payload["evidence_plan_available"] is True
    assert payload["objective_compiler_workflow_ready"] is True
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v5.8.0"


def test_objective_compiler_workflow_turns_clear_goal_into_contract_and_dag(tmp_path: Path) -> None:
    payload = build_objective_compiler_workflow(
        home=tmp_path,
        objective="제우스야, repo를 분석하고 보안 개선안을 evidence-backed workflow로 만들어줘.",
        session_id="session.v550",
        principal_id="operator.local",
        task_count=5,
        requires_code=True,
        requires_research=True,
        risk_level="high",
    ).to_payload()

    assert payload["decision"] == "compiled"
    assert payload["target_version"] == "v5.5.0"
    assert payload["objective_understood"] is True
    assert payload["interview_required"] is False
    assert payload["objective_contract_ready"] is True
    assert payload["workflow_dag_ready"] is True
    assert payload["selected_pattern"] == "adversarial_verification"
    assert payload["evidence_plan"]
    assert payload["authority_requirements"]
    assert payload["objective_run"]["completion_summary"]["status"] == "blocked_missing_evidence"
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_objective_compiler_workflow_requires_interview_for_vague_goal(tmp_path: Path) -> None:
    payload = build_objective_compiler_workflow(
        home=tmp_path,
        objective="제우스야, 개선해줘",
        session_id="session.v550.vague",
        principal_id="operator.local",
    ).to_payload()

    assert payload["decision"] == "needs_interview"
    assert payload["objective_understood"] is False
    assert payload["interview_required"] is True
    assert payload["interview_questions"]
    assert "desired_outcome" in payload["intent_frame"]["unknowns"]
    assert payload["workflow_dag_ready"] is False
    assert payload["handler_executed"] is False


def test_cli_and_library_expose_objective_compiler_workflow(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        [
            "objective-compile-workflow",
            "--objective",
            "Zeus, compile a coding objective into a governed workflow.",
            "--session-id",
            "session.v550.cli",
            "--principal-id",
            "operator.local",
            "--requires-code",
            "--task-count",
            "4",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).objective_compile_workflow(
        objective="Zeus, compile a coding objective into a governed workflow.",
        session_id="session.v550.cli.library",
        principal_id="operator.local",
        requires_code=True,
        task_count=4,
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == "v5.5.0"
    assert library_payload["target_version"] == "v5.5.0"
    assert cli_payload["objective_compiler_workflow_ready"] is True
    assert library_payload["objective_compiler_workflow_ready"] is True
    assert cli_payload["handler_executed"] is False
    assert library_payload["handler_executed"] is False
