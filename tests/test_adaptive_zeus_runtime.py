from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.adaptive_zeus_runtime import build_adaptive_zeus_contract
from zeus_agent.cli import app
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v010_release_gate_reports_adaptive_zeus_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v0.10.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.10.0"
    assert payload["release_stage"] == "adaptive_zeus"
    assert payload["adaptive_zeus_contract_available"] is True
    assert payload["dynamic_workflow_contract_available"] is True
    assert payload["pattern_router_contract_available"] is True
    assert payload["critique_checkpoint_contract_available"] is True
    assert payload["workflow_learning_contract_available"] is True
    assert payload["trajectory_eval_contract_available"] is True
    assert payload["adaptive_zeus_ready"] is False
    assert "adaptive_zeus_release_gate_manual_qa" in payload["required_checkpoint_evidence"]
    assert "adaptive_zeus_secret_boundary_manual_qa" in payload["required_checkpoint_evidence"]
    assert "memory_ontology_release_gate_manual_qa" not in payload["required_checkpoint_evidence"]
    assert payload["workflow_self_modification"] is False
    assert payload["workflow_memory_auto_write"] is False
    assert payload["authority_widened"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["next_version"] == "v1.0.0-rc"
    assert payload["no_secret_echo"] is True


def test_adaptive_zeus_contract_selects_fan_out_for_broad_code_work() -> None:
    result = build_adaptive_zeus_contract(
        objective="Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
        requires_research=True,
        risk_level="normal",
        evidence_target="v010.evidence.fanout",
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v0.10.0"
    assert payload["objective_contract_id"] == "zeus.v0.10.0.adaptive_zeus"
    assert payload["selected_pattern"] == "fan_out_and_synthesize"
    assert payload["why_not_decision"] == "fan_out"
    assert payload["pattern_changed_from_default"] is True
    assert payload["parallel_wave_count"] == 2
    assert payload["parallel_task_count"] == 4
    assert payload["review_required"] is True
    assert "lean_ulw" in payload["rejected_alternatives"]
    assert "disjoint_write_scopes_required" in payload["safety_notes"]
    assert payload["workflow_self_modification"] is False
    assert payload["workflow_memory_auto_write"] is False
    assert payload["authority_widened"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_adaptive_zeus_contract_selects_lean_or_adversarial_patterns() -> None:
    lean = build_adaptive_zeus_contract(
        objective="Polish one local documentation typo",
        task_count=1,
        risk_level="low",
        evidence_target="v010.evidence.lean",
    ).to_payload()
    adversarial = build_adaptive_zeus_contract(
        objective="Implement sensitive approval policy",
        task_count=3,
        requires_code=True,
        risk_level="high",
        evidence_target="v010.evidence.adversarial",
    ).to_payload()

    assert lean["decision"] == "report"
    assert lean["selected_pattern"] == "lean_ulw"
    assert lean["why_not_decision"] == "lean_down"
    assert lean["parallel_wave_count"] == 1
    assert lean["review_required"] is False
    assert adversarial["decision"] == "report"
    assert adversarial["selected_pattern"] == "adversarial_verification"
    assert adversarial["why_not_decision"] == "adversarial_review"
    assert adversarial["review_required"] is True
    assert "high_risk_requires_independent_review" in adversarial["safety_notes"]
    assert adversarial["network_opened"] is False


def test_adaptive_zeus_cli_and_library_surface_match(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "adaptive-zeus",
            "--objective",
            "Implement provider, MCP catalog, cron, and review slices",
            "--task-count",
            "5",
            "--requires-code",
            "--requires-research",
            "--risk-level",
            "normal",
            "--evidence-target",
            "v010.evidence.cli",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).adaptive_zeus_status(
        objective="Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
        requires_research=True,
        risk_level="normal",
        evidence_target="v010.evidence.cli",
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == library_payload
    assert library_payload["selected_pattern"] == "fan_out_and_synthesize"
    assert library_payload["network_opened"] is False


def test_adaptive_zeus_blocks_secret_like_objective_without_echo() -> None:
    raw_secret = "".join(("sk", "-", "v010-adaptive-secret"))
    result = CliRunner().invoke(
        app,
        [
            "adaptive-zeus",
            "--objective",
            "Use token={0} to optimize the workflow".format(raw_secret),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True).lower()
    assert payload["decision"] == "blocked"
    assert payload["selected_objective"] == "unknown"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized
