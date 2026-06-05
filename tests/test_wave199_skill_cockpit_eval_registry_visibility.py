from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.skill_cockpit_runtime import SkillCockpitRuntime
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime


def test_skill_cockpit_surfaces_ready_eval_registry_record(tmp_path: Path) -> None:
    eval_result = SkillEvalRuntime(tmp_path).evaluate(candidate_id="review-checklist")
    SkillEvalRegistryRuntime(tmp_path).record(
        eval_result=eval_result,
        eval_ref="skill-eval://wave199/ready",
    )

    result = SkillCockpitRuntime(tmp_path).build(candidate_id="review-checklist")

    assert result.decision == "report"
    assert result.eval_record_count == 1
    assert result.eval_ready_for_review_count == 1
    assert result.eval_blocked_count == 0
    assert result.selected_candidate is not None
    assert result.selected_candidate["candidate_id"] == "review-checklist"
    assert result.selected_candidate["eval_record_count"] == 1
    assert result.selected_candidate["latest_eval_status"] == "ready_for_review"
    assert result.selected_candidate["latest_eval_score"] == 100
    assert result.selected_candidate["latest_eval_record_id"] is not None
    assert result.active_skill_written is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_skill_cockpit_surfaces_blocked_eval_registry_record(tmp_path: Path) -> None:
    eval_result = SkillEvalRuntime(tmp_path).evaluate(candidate_id="unsafe-auto-promotion")
    SkillEvalRegistryRuntime(tmp_path).record(
        eval_result=eval_result,
        eval_ref="skill-eval://wave199/blocked",
    )

    result = SkillCockpitRuntime(tmp_path).build(candidate_id="unsafe-auto-promotion")

    assert result.decision == "report"
    assert result.eval_record_count == 1
    assert result.eval_ready_for_review_count == 0
    assert result.eval_blocked_count == 1
    assert result.selected_candidate is not None
    assert result.selected_candidate["candidate_id"] == "unsafe-auto-promotion"
    assert result.selected_candidate["eval_record_count"] == 1
    assert result.selected_candidate["latest_eval_status"] == "blocked"
    assert result.selected_candidate["latest_eval_score"] < 80
    assert result.no_secret_echo is True
    assert result.active_rule_written is False


def test_skill_cockpit_eval_registry_cli_and_library_surface_match(tmp_path: Path) -> None:
    eval_result = SkillEvalRuntime(tmp_path).evaluate(candidate_id="review-checklist")
    SkillEvalRegistryRuntime(tmp_path).record(
        eval_result=eval_result,
        eval_ref="skill-eval://wave199/cli",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "skills",
            "--home",
            str(tmp_path),
            "--candidate-id",
            "review-checklist",
            "--json",
        ],
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    library_payload = ZeusAgent(home=tmp_path).skill_status(candidate_id="review-checklist")

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads(completed.stdout)
    assert cli_payload == library_payload
    assert cli_payload["eval_record_count"] == 1
    assert cli_payload["selected_candidate"]["latest_eval_status"] == "ready_for_review"
