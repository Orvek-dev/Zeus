from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.eval.wave19 import run_wave19_eval


def test_wave19_cli_outputs_research_provider_payloads_without_live_io() -> None:
    # Given: the package CLI registered Wave19 research provider commands.
    runner = CliRunner()

    # When: happy and block scenarios are executed through the real CLI surface.
    happy = runner.invoke(app, ["wave19-research-provider", "--scenario", "pinned-fake", "--json"])
    blocks = runner.invoke(
        app,
        ["wave19-research-provider-blocks", "--secret-like", "sk-wave19-cli-secret", "--json"],
    )

    # Then: both commands return structured JSON and do not leak secret-like input.
    assert happy.exit_code == 0, happy.stdout
    assert blocks.exit_code == 0, blocks.stdout
    happy_payload = json.loads(happy.stdout)
    block_payload = json.loads(blocks.stdout)
    assert happy_payload["scenario_id"] == "C001"
    assert happy_payload["web_provider_created"] is True
    assert happy_payload["github_provider_created"] is True
    assert happy_payload["network_opened"] is False
    assert block_payload["scenario_id"] == "C002"
    assert block_payload["stale_web_source"] == "blocked"
    assert block_payload["secret_github_query"] == "blocked"
    assert "sk-wave19-cli-secret" not in blocks.stdout


def test_wave19_eval_reports_research_provider_suite_without_production_claim() -> None:
    # Given: Wave19 fake research provider happy and adversarial scenarios.
    payload = run_wave19_eval()

    # When / Then: the eval summarizes source pinning and no-production-claim status.
    assert payload["suite"] == "wave19"
    assert payload["failed"] == 0
    assert payload["research_provider_happy_passed"] is True
    assert payload["research_provider_blocks_passed"] is True
    assert payload["live_production_claimed"] is False
