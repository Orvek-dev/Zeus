from __future__ import annotations

from pathlib import Path

from zeus_agent.eval.golden_journeys import run_golden_journeys


def test_golden_journeys_cover_setup_chat_catalog_workflow_research_and_cron(tmp_path: Path) -> None:
    # Given: a local Zeus home for dry-run product journeys.
    payload = run_golden_journeys(home=tmp_path)

    # Then: each journey passes without live production claims or network side effects.
    assert payload["journey_count"] >= 6
    assert payload["passed_count"] == payload["journey_count"]
    assert payload["failed_count"] == 0
    assert payload["live_production_claimed"] is False
    assert payload["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert {item["journey_id"] for item in payload["journeys"]} >= {
        "first_chat",
        "setup_doctor",
        "mcp_catalog",
        "adaptive_workflow",
        "research_brief",
        "cron_security_block",
    }
