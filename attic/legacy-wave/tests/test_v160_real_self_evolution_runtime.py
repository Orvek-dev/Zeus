from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.real_self_evolution_runtime import build_real_self_evolution_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v160_release_gate_reports_self_evolution_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.6.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.6.0"
    assert payload["release_stage"] == "self_evolution_production_loop"
    assert payload["real_self_evolution_contract_available"] is True
    assert payload["skill_eval_runtime_available"] is True
    assert payload["skill_learning_runtime_available"] is True
    assert payload["workflow_learning_runtime_available"] is True
    assert payload["promotion_review_gate_available"] is True
    assert payload["real_self_evolution_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v1.7.0"
    assert "real_self_evolution_eval_learning_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_real_self_evolution_status_reports_surfaces_without_writes() -> None:
    result = build_real_self_evolution_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.6.0"
    assert payload["objective_contract_id"] == "zeus.v1.6.0.self_evolution_production_loop"
    assert payload["skill_eval_runtime_available"] is True
    assert payload["skill_learning_runtime_available"] is True
    assert payload["workflow_learning_runtime_available"] is True
    assert payload["memory_write_executed"] is False
    assert payload["active_skill_written"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_self_evolution_eval_learning_records_reviewable_candidate() -> None:
    result = build_real_self_evolution_contract(scenario="eval-learning-smoke")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["eval_learning_ready"] is True
    assert payload["eval_record_count"] >= 1
    assert payload["learning_candidate_count"] >= 1
    assert payload["skill_eval_contract"]["promotion_allowed"] is False
    assert payload["skill_learning_contract"]["review_required_count"] >= 1
    assert payload["active_skill_written"] is False
    assert payload["active_rule_written"] is False
    assert payload["authority_widened"] is False
    assert payload["no_secret_echo"] is True


def test_real_self_evolution_skill_proposal_keeps_candidate_review_required() -> None:
    result = build_real_self_evolution_contract(scenario="skill-proposal-smoke")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["skill_proposal_ready"] is True
    assert payload["skill_candidate_count"] == 1
    assert payload["promotion_review_contract"]["status"] == "review_required"
    assert "explicit_review_required" in payload["blocked_reasons"]
    assert payload["skill_auto_promotion"] is False
    assert payload["active_skill_written"] is False
    assert payload["no_secret_echo"] is True


def test_real_self_evolution_workflow_critique_memory_records_local_fact_only() -> None:
    result = build_real_self_evolution_contract(scenario="workflow-critique-memory")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["workflow_critique_memory_ready"] is True
    assert payload["fact_count"] >= 1
    assert payload["workflow_learning_contract"]["decision"] == "recorded"
    assert payload["workflow_learning_contract"]["memory_promoted"] is False
    assert payload["workflow_pattern_promoted"] is False
    assert payload["authority_widened"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_self_evolution_promotion_block_prevents_active_writes() -> None:
    result = build_real_self_evolution_contract(scenario="promotion-block")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert payload["promotion_block_ready"] is True
    assert "explicit_review_required" in payload["blocked_reasons"]
    assert payload["memory_auto_promotion"] is False
    assert payload["skill_auto_promotion"] is False
    assert payload["active_skill_written"] is False
    assert payload["active_rule_written"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_real_self_evolution_secret_marker_is_blocked_without_echo() -> None:
    result = build_real_self_evolution_contract(
        scenario="eval-learning-smoke",
        objective="Improve workflow with sk-v160-self-evolution-secret",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert "sk-v160-self-evolution-secret" not in serialized
    assert payload["raw_secret_returned"] is False
    assert payload["no_secret_echo"] is True


def test_real_self_evolution_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "self-evolution-runtime",
            "--home",
            str(tmp_path),
            "--scenario",
            "workflow-critique-memory",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).self_evolution_runtime(
        scenario="workflow-critique-memory",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["workflow_critique_memory_ready"] is True
    assert library_payload["workflow_critique_memory_ready"] is True
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
