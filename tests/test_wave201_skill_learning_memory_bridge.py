from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.memory_cockpit_runtime import MemoryCockpitRuntime
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime
from zeus_agent.skill_learning_runtime import SkillLearningMemoryRuntime


def test_skill_learning_memory_record_writes_reviewable_prometheus_fact(tmp_path: Path) -> None:
    _record_eval(tmp_path, "review-checklist", "skill-eval://wave201/ready")

    result = SkillLearningMemoryRuntime(tmp_path).record(candidate_id="review-checklist")
    memory = MemoryCockpitRuntime(tmp_path).build(subject="Prometheus")

    assert result.decision == "recorded"
    assert result.selected_fact is not None
    assert result.selected_fact["subject"] == "Prometheus"
    assert result.selected_fact["predicate"] == "skill_eval_learning_candidate"
    assert result.selected_fact["status"] == "proposed"
    assert "review-checklist" in result.selected_fact["object_text"]
    assert "ready_for_review" in result.selected_fact["object_text"]
    assert result.fact_count == 1
    assert result.memory_promoted is False
    assert result.active_skill_written is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert memory.wiki_page is not None
    assert "review-checklist" in memory.wiki_page["body"]


def test_skill_learning_memory_record_blocks_unknown_learning(tmp_path: Path) -> None:
    _record_eval(tmp_path, "review-checklist", "skill-eval://wave201/ready")

    result = SkillLearningMemoryRuntime(tmp_path).record(candidate_id="missing-candidate")
    memory = MemoryCockpitRuntime(tmp_path).build(subject="Prometheus")

    assert result.decision == "blocked"
    assert result.selected_fact is None
    assert result.blocked_reasons == ("unknown_skill_learning_candidate",)
    assert result.fact_count == 0
    assert result.memory_promoted is False
    assert memory.fact_count == 0


def test_skill_learning_memory_cli_and_library_surfaces_write_local_facts(tmp_path: Path) -> None:
    cli_home = tmp_path / "cli"
    library_home = tmp_path / "library"
    _record_eval(cli_home, "review-checklist", "skill-eval://wave201/cli")
    _record_eval(library_home, "review-checklist", "skill-eval://wave201/library")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "skill-learning-memory-record",
            "--home",
            str(cli_home),
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
    library_payload = ZeusAgent(home=library_home).skill_learning_memory_record(
        candidate_id="review-checklist"
    )

    assert completed.returncode == 0, completed.stderr
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["decision"] == "recorded"
    assert library_payload["decision"] == "recorded"
    assert cli_payload["selected_fact"]["status"] == "proposed"
    assert library_payload["selected_fact"]["status"] == "proposed"
    assert cli_payload["live_production_claimed"] is False
    assert library_payload["live_production_claimed"] is False


def _record_eval(tmp_path: Path, candidate_id: str, eval_ref: str) -> None:
    eval_result = SkillEvalRuntime(tmp_path).evaluate(candidate_id=candidate_id)
    SkillEvalRegistryRuntime(tmp_path).record(eval_result=eval_result, eval_ref=eval_ref)
