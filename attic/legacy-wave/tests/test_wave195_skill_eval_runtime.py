from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryRuntime,
)
from zeus_agent.skill_eval_runtime import SkillEvalRuntime
from tests.test_wave191_live_research_workflow_ontology_registry import _workflow_ingestion


def test_skill_eval_marks_safe_candidate_ready_for_review_without_promotion() -> None:
    result = SkillEvalRuntime().evaluate(candidate_id="review-checklist")

    assert result.decision == "evaluated"
    assert result.candidate_id == "review-checklist"
    assert result.eval_status == "ready_for_review"
    assert result.score >= 80
    assert result.promotion_allowed is False
    assert result.active_skill_written is False
    assert result.active_rule_written is False
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_skill_eval_blocks_unsafe_auto_promotion_candidate() -> None:
    result = SkillEvalRuntime().evaluate(candidate_id="unsafe-auto-promotion")

    assert result.decision == "evaluated"
    assert result.eval_status == "blocked"
    assert result.score < 80
    assert "auto_promotion_requested" in result.blocked_reasons
    assert "live_transport_enablement_requested" in result.blocked_reasons
    assert result.promotion_allowed is False
    assert result.active_skill_written is False


def test_skill_eval_scores_ontology_derived_candidate_from_local_home(tmp_path: Path) -> None:
    registry = _record_workflow_candidate(tmp_path, "skill-eval")

    result = SkillEvalRuntime(tmp_path).evaluate(candidate_id=registry.candidate_id)

    assert result.decision == "evaluated"
    assert result.eval_status == "ready_for_review"
    assert result.source == "ontology_review_queue"
    assert result.source_candidate_id == registry.candidate_id
    assert result.score >= 80
    assert result.promotion_allowed is False
    assert result.network_opened is False


def test_skill_eval_cli_exposes_ontology_derived_candidate(tmp_path: Path) -> None:
    registry = _record_workflow_candidate(tmp_path, "cli")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "skill-eval",
            "--home",
            str(tmp_path),
            "--candidate-id",
            registry.candidate_id or "",
            "--json",
        ],
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "evaluated"
    assert payload["eval_status"] == "ready_for_review"
    assert payload["source"] == "ontology_review_queue"
    assert payload["promotion_allowed"] is False
    assert payload["live_production_claimed"] is False


def _record_workflow_candidate(tmp_path: Path, tag: str):
    ingestion = _workflow_ingestion("wave195-{0}".format(tag))
    return LiveResearchWorkflowOntologyRegistryRuntime(tmp_path).record(
        workflow_ingestion=ingestion,
        record_ref="ontology-candidate-record://wave195/{0}".format(tag),
    )
