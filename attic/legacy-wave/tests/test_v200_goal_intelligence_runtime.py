from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.goal_intelligence_runtime import build_goal_intelligence_contract
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v200_release_gate_reports_goal_intelligence_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v2.0.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v2.0.0"
    assert payload["release_stage"] == "goal_intelligence_adaptive_execution_platform"
    assert payload["goal_intelligence_contract_available"] is True
    assert payload["objective_understanding_runtime_available"] is True
    assert payload["deep_interview_runtime_available"] is True
    assert payload["user_context_model_available"] is True
    assert payload["context_ontology_runtime_available"] is True
    assert payload["adaptive_replanning_runtime_available"] is True
    assert payload["workflow_critic_runtime_available"] is True
    assert payload["eval_loop_runtime_available"] is True
    assert payload["goal_intelligence_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v2.1.0"
    assert "goal_intelligence_objective_understanding_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_goal_intelligence_status_composes_existing_safe_runtimes(tmp_path: Path) -> None:
    result = build_goal_intelligence_contract(scenario="status", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v2.2.0"
    assert payload["objective_contract_id"] == "zeus.v2.2.0.goal_intelligence_platform"
    assert payload["goal_intelligence_ready"] is True
    assert payload["objective_understood"] is True
    assert payload["adaptive_replan_ready"] is True
    assert payload["eval_loop_ready"] is True
    assert payload["production_ready"] is False
    assert payload["workflow_self_modification"] is False
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_goal_intelligence_understands_broad_user_objective(tmp_path: Path) -> None:
    result = build_goal_intelligence_contract(
        scenario="understand-objective",
        home=tmp_path,
        objective="Build a parallel coding workflow that researches GitHub, MCP tools, and safe sandbox execution.",
        task_count=7,
        requires_code=True,
        requires_research=True,
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["objective_understood"] is True
    assert payload["interview_required"] is False
    assert payload["normalized_objective"].startswith("Build a parallel coding workflow")
    assert "desired_outcome" in payload["user_context_model"]
    assert payload["user_context_model"]["workflow_shape"] == "parallel_research_and_code"
    assert payload["authority_widened"] is False


def test_goal_intelligence_deep_interview_creates_context_candidate_without_memory_write(tmp_path: Path) -> None:
    result = build_goal_intelligence_contract(
        scenario="deep-interview",
        home=tmp_path,
        objective="Make Zeus understand my goal and choose a better execution loop.",
        task_count=3,
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["deep_interview_ready"] is True
    assert payload["interview_question_count"] >= 1
    assert payload["user_context_update_candidate"] is True
    assert payload["workflow_memory_auto_write"] is False
    assert payload["memory_write_executed"] is False
    assert payload["active_rule_written"] is False


def test_goal_intelligence_adaptive_replan_uses_parallel_critic_for_code_and_research(tmp_path: Path) -> None:
    result = build_goal_intelligence_contract(
        scenario="adaptive-replan",
        home=tmp_path,
        objective=(
            "Implement provider, MCP, gateway, and sandbox live platform slices "
            "with approval, lease, audit evidence, and independent review."
        ),
        task_count=8,
        requires_code=True,
        requires_research=True,
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["adaptive_replan_ready"] is True
    assert payload["workflow_critic_ready"] is True
    assert payload["adaptive_contract"]["selected_pattern"] == "fan_out_and_synthesize"
    assert payload["parallel_task_count"] >= 4
    assert payload["authority_widened"] is False
    assert payload["live_production_claimed"] is False


def test_goal_intelligence_context_ontology_uses_local_reviewable_memory_only(tmp_path: Path) -> None:
    result = build_goal_intelligence_contract(
        scenario="ontology-context",
        home=tmp_path,
        objective="Organize what Zeus learned about my coding workflow into ontology context.",
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["context_ontology_ready"] is True
    assert payload["memory_contract"]["ontology_wiki_ready"] is True
    assert payload["ontology_candidate_count"] >= 0
    assert payload["memory_write_executed"] is True
    assert payload["memory_auto_promotion"] is False
    assert payload["ontology_auto_promotion"] is False
    assert payload["wiki_page_update_written"] is False
    assert payload["no_secret_echo"] is True


def test_goal_intelligence_secret_marker_is_blocked_without_echo(tmp_path: Path) -> None:
    result = build_goal_intelligence_contract(
        scenario="understand-objective",
        home=tmp_path,
        objective="Use this key sk-v200-live-secret to plan the workflow.",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert "sk-v200-live-secret" not in serialized
    assert payload["raw_secret_returned"] is False
    assert payload["no_secret_echo"] is True


def test_goal_intelligence_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "goal-intelligence-runtime",
            "--home",
            str(tmp_path),
            "--scenario",
            "adaptive-replan",
            "--objective",
            "Build a research backed coding workflow with parallel workers.",
            "--task-count",
            "6",
            "--requires-code",
            "--requires-research",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).goal_intelligence_runtime(
        scenario="adaptive-replan",
        objective="Build a research backed coding workflow with parallel workers.",
        task_count=6,
        requires_code=True,
        requires_research=True,
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["adaptive_replan_ready"] is True
    assert library_payload["workflow_critic_ready"] is True
    assert cli_payload["production_ready"] is False
