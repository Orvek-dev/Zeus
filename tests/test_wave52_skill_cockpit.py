from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.skill_cockpit_runtime import SkillCockpitRuntime


def test_skill_cockpit_reports_prometheus_candidates_without_promotion() -> None:
    result = SkillCockpitRuntime().build()

    assert result.decision == "report"
    assert result.candidate_count == 2
    assert result.review_required_count == 1
    assert result.blocked_candidate_count == 1
    assert result.promoted_candidate_count == 0
    assert result.selected_candidate is None
    assert "zeus skills --candidate-id review-checklist --json" in result.recommended_next_commands
    assert result.active_skill_written is False
    assert result.active_rule_written is False
    assert result.authority_widened is False
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_skill_cockpit_inspects_review_required_candidate() -> None:
    result = SkillCockpitRuntime().build(candidate_id="review-checklist")

    assert result.decision == "report"
    assert result.selected_candidate is not None
    assert result.selected_candidate["candidate_id"] == "review-checklist"
    assert result.selected_candidate["review_status"] == "review_required"
    assert result.selected_candidate["promoted"] is False
    assert result.selected_candidate["active_skill_written"] is False
    assert result.selected_candidate["blocked_reasons"] == ["explicit_review_required"]


def test_skill_cockpit_blocks_unsafe_auto_promotion_without_secret_echo() -> None:
    raw_secret = "sk-" + "wave52-secret"
    result = SkillCockpitRuntime().build(candidate_id="unsafe-auto-promotion")
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    assert result.decision == "report"
    assert result.selected_candidate is not None
    assert result.selected_candidate["review_status"] == "blocked"
    assert "auto_promotion_requested" in result.selected_candidate["blocked_reasons"]
    assert "live_transport_enablement_requested" in result.selected_candidate["blocked_reasons"]
    assert raw_secret not in serialized
    assert result.no_secret_echo is True
    assert result.active_rule_written is False
    assert result.network_opened is False


def test_skill_cockpit_blocks_unknown_candidate_inspection() -> None:
    result = SkillCockpitRuntime().build(candidate_id="unknown")

    assert result.decision == "blocked"
    assert result.selected_candidate is None
    assert result.blocked_reasons == ("unknown_skill_candidate",)
    assert result.promoted_candidate_count == 0
    assert result.live_production_claimed is False


def test_cli_exposes_skill_cockpit_inspection() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "skills", "--candidate-id", "review-checklist", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "report"
    assert payload["selected_candidate"]["candidate_id"] == "review-checklist"
    assert payload["selected_candidate"]["review_status"] == "review_required"
    assert payload["active_skill_written"] is False
    assert payload["handler_executed"] is False


def test_python_library_exposes_skill_cockpit() -> None:
    payload = ZeusAgent().skill_status(candidate_id="unsafe-auto-promotion")

    assert payload["decision"] == "report"
    assert payload["selected_candidate"]["candidate_id"] == "unsafe-auto-promotion"
    assert payload["selected_candidate"]["review_status"] == "blocked"
    assert payload["live_production_claimed"] is False
