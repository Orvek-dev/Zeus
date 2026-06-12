from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime


def test_skill_eval_registry_records_ready_and_blocked_eval_results(tmp_path: Path) -> None:
    ready = SkillEvalRuntime(tmp_path).evaluate(candidate_id="review-checklist")
    blocked = SkillEvalRuntime(tmp_path).evaluate(candidate_id="unsafe-auto-promotion")
    runtime = SkillEvalRegistryRuntime(tmp_path)

    ready_record = runtime.record(eval_result=ready, eval_ref="skill-eval://wave198/ready")
    blocked_record = runtime.record(eval_result=blocked, eval_ref="skill-eval://wave198/blocked")
    listed = runtime.list()

    assert ready_record.decision == "recorded"
    assert blocked_record.decision == "recorded"
    assert ready_record.eval_status == "ready_for_review"
    assert blocked_record.eval_status == "blocked"
    assert listed.decision == "listed"
    assert listed.record_count == 2
    assert listed.ready_for_review_count == 1
    assert listed.blocked_eval_count == 1
    assert listed.promotion_allowed is False
    assert listed.active_skill_written is False
    assert listed.active_rule_written is False
    assert listed.authority_widened is False
    assert listed.network_opened is False
    assert listed.live_production_claimed is False


def test_skill_eval_registry_blocks_eval_side_effects(tmp_path: Path) -> None:
    unsafe = SkillEvalRuntime(tmp_path).evaluate(candidate_id="review-checklist").model_copy(
        update={"active_skill_written": True, "promotion_allowed": True}
    )

    result = SkillEvalRegistryRuntime(tmp_path).record(
        eval_result=unsafe,
        eval_ref="skill-eval://wave198/unsafe",
    )

    assert result.decision == "blocked"
    assert "skill_eval_promotion_or_activation_detected" in result.blocked_reasons
    assert result.record_count == 0
    assert result.active_skill_written is False
    assert result.promotion_allowed is False
    assert result.network_opened is False


def test_skill_eval_registry_cli_and_library_surface_match(tmp_path: Path) -> None:
    eval_result = SkillEvalRuntime(tmp_path).evaluate(candidate_id="review-checklist")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "skill-eval-record",
            "--home",
            str(tmp_path),
            "--eval-json",
            eval_result.model_dump_json(),
            "--eval-ref",
            "skill-eval://wave198/cli",
            "--json",
        ],
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    listed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "skill-eval-records",
            "--home",
            str(tmp_path),
            "--json",
        ],
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    library_record = ZeusAgent(home=tmp_path).skill_eval_record(
        eval_result=eval_result.to_payload(),
        eval_ref="skill-eval://wave198/library",
    )
    library_list = ZeusAgent(home=tmp_path).skill_eval_records()

    assert completed.returncode == 0, completed.stderr
    assert listed.returncode == 0, listed.stderr
    completed_payload = json.loads(completed.stdout)
    listed_payload = json.loads(listed.stdout)
    assert completed_payload["decision"] == "recorded"
    assert listed_payload["record_count"] == 1
    assert library_record["decision"] == "recorded"
    assert library_list["record_count"] == 2
    assert library_list["ready_for_review_count"] == 2
    assert library_list["promotion_allowed"] is False
