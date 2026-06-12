from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.research_cockpit_runtime import ResearchCockpitRuntime


def test_research_cockpit_reports_source_lanes_without_live_search() -> None:
    result = ResearchCockpitRuntime().build(query="parallel coding orchestration")

    assert result.decision == "report"
    assert result.source_lane_count == 4
    assert result.source_pin_required_count == 4
    assert result.live_enabled_count == 0
    assert result.selected_source is None
    assert result.brief_preview["provider_count"] == 2
    assert result.brief_preview["external_claims_pinned"] is True
    assert "zeus research --source github --query <query> --json" in result.recommended_next_commands
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.live_production_claimed is False


def test_research_cockpit_inspects_github_source_lane() -> None:
    result = ResearchCockpitRuntime().build(source_id="github", query="tmux codex orchestration")

    assert result.decision == "report"
    assert result.selected_source is not None
    assert result.selected_source["source_id"] == "github"
    assert result.selected_source["source_kind"] == "github_source_pin"
    assert result.selected_source["requires_source_pin"] is True
    assert result.selected_source["live_adapter_enabled"] is False
    assert result.selected_source["freshness_required"] == "fresh"
    assert result.network_opened is False


def test_research_cockpit_redacts_secret_query_before_brief_preview() -> None:
    raw_secret = "sk-" + "wave55-secret"
    result = ResearchCockpitRuntime().build(query="latest agent workflow {0}".format(raw_secret))
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    assert raw_secret not in serialized
    assert result.no_secret_echo is True
    assert result.brief_preview["query"] == "latest agent workflow sk-...redacted"
    assert result.network_opened is False


def test_research_cockpit_blocks_unknown_source_lane() -> None:
    result = ResearchCockpitRuntime().build(source_id="unknown", query="agent workflow")

    assert result.decision == "blocked"
    assert result.selected_source is None
    assert result.blocked_reasons == ("unknown_research_source",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_exposes_research_cockpit_inspection() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "research",
            "--source",
            "github",
            "--query",
            "tmux codex orchestration",
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "report"
    assert payload["selected_source"]["source_id"] == "github"
    assert payload["brief_preview"]["provider_count"] == 2
    assert payload["network_opened"] is False


def test_python_library_exposes_research_cockpit() -> None:
    payload = ZeusAgent().research_status(source_id="web", query="agent workflow")

    assert payload["decision"] == "report"
    assert payload["selected_source"]["source_id"] == "web"
    assert payload["selected_source"]["live_adapter_enabled"] is False
    assert payload["live_production_claimed"] is False
