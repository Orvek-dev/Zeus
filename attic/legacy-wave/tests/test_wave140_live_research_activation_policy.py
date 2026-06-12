from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime


def test_live_research_policy_reports_source_lane_without_network() -> None:
    result = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=False,
    )

    assert result.decision == "policy_ready"
    assert result.source_known is True
    assert result.live_search_allowed is False
    assert result.source_pin_required is True
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.live_production_claimed is False


def test_live_research_policy_plans_live_search_with_approval_and_source_pin() -> None:
    result = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        approval_ref="approval://research/github",
        source_pin_ref="source-pin://research/github",
        max_results=5,
        rate_limit_per_minute=30,
    )

    assert result.decision == "activation_planned"
    assert result.live_search_allowed is True
    assert result.approval_bound is True
    assert result.source_pin_bound is True
    assert result.network_opened is False
    assert result.client_constructed is False


def test_live_research_policy_blocks_missing_controls_and_budget_overflow() -> None:
    result = LiveResearchActivationPolicyRuntime().plan(
        source_id="web",
        query="live search",
        live_search_requested=True,
        max_results=100,
        rate_limit_per_minute=500,
    )

    assert result.decision == "blocked"
    assert "live_research_requires_approval" in result.blocked_reasons
    assert "source_pin_ref_required" in result.blocked_reasons
    assert "max_results_limit_exceeded" in result.blocked_reasons
    assert "rate_limit_exceeded" in result.blocked_reasons


def test_cli_and_python_library_live_research_policy() -> None:
    completed = CliRunner().invoke(
        app,
        [
            "live-research-activation-policy",
            "--source-id",
            "github",
            "--query",
            "parallel coding workflow",
            "--live-search-requested",
            "--approval-ref",
            "approval://research/github",
            "--source-pin-ref",
            "source-pin://research/github",
            "--max-results",
            "5",
            "--rate-limit-per-minute",
            "30",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "activation_planned"
    assert payload["network_opened"] is False

    library_payload = ZeusAgent().live_research_activation_policy(
        source_id="unknown",
        query="workflow",
    )
    assert library_payload["decision"] == "blocked"
    assert "unknown_research_source" in library_payload["blocked_reasons"]
