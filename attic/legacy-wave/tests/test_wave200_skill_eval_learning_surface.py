from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime
from zeus_agent.skill_learning_runtime import SkillLearningRuntime


def test_skill_learning_runtime_derives_prometheus_candidates_from_eval_records(tmp_path: Path) -> None:
    _record_eval(tmp_path, "review-checklist", "skill-eval://wave200/ready")
    _record_eval(tmp_path, "unsafe-auto-promotion", "skill-eval://wave200/blocked")

    result = SkillLearningRuntime(tmp_path).build(candidate_id="unsafe-auto-promotion")

    assert result.decision == "report"
    assert result.eval_record_count == 2
    assert result.learning_candidate_count == 2
    assert result.ready_learning_count == 1
    assert result.blocked_learning_count == 1
    assert result.review_required_count == 2
    assert result.promoted_candidate_count == 0
    assert result.selected_learning is not None
    assert result.selected_learning["source"] == "skill_eval_registry"
    assert result.selected_learning["candidate_id"] == "unsafe-auto-promotion"
    assert result.selected_learning["eval_status"] == "blocked"
    assert result.selected_learning["review_status"] == "review_required"
    assert result.selected_learning["promoted"] is False
    assert result.selected_learning["active_skill_written"] is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_skill_learning_runtime_blocks_unknown_selection(tmp_path: Path) -> None:
    _record_eval(tmp_path, "review-checklist", "skill-eval://wave200/ready")

    result = SkillLearningRuntime(tmp_path).build(candidate_id="missing-candidate")

    assert result.decision == "blocked"
    assert result.selected_learning is None
    assert result.blocked_reasons == ("unknown_skill_learning_candidate",)
    assert result.promoted_candidate_count == 0
    assert result.active_rule_written is False


def test_skill_learning_cli_and_library_surface_match(tmp_path: Path) -> None:
    _record_eval(tmp_path, "review-checklist", "skill-eval://wave200/cli")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "skill-learnings",
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
    library_payload = ZeusAgent(home=tmp_path).skill_learnings(candidate_id="review-checklist")

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads(completed.stdout)
    assert cli_payload == library_payload
    assert cli_payload["learning_candidate_count"] == 1
    assert cli_payload["selected_learning"]["eval_status"] == "ready_for_review"
    assert cli_payload["selected_learning"]["review_status"] == "review_required"


def _record_eval(tmp_path: Path, candidate_id: str, eval_ref: str) -> None:
    eval_result = SkillEvalRuntime(tmp_path).evaluate(candidate_id=candidate_id)
    SkillEvalRegistryRuntime(tmp_path).record(eval_result=eval_result, eval_ref=eval_ref)
