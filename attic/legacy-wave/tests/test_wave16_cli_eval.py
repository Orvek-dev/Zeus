from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.eval.wave16 import run_wave16_eval


def test_wave16_cli_outputs_live_provider_happy_and_block_payloads() -> None:
    # Given: the package CLI registered Wave16 live provider commands.
    runner = CliRunner()

    # When: happy and block scenarios are executed through the real CLI surface.
    happy = runner.invoke(app, ["wave16-provider-live", "--scenario", "loopback", "--json"])
    blocks = runner.invoke(
        app,
        ["wave16-provider-live-blocks", "--secret-like", "sk-wave16-cli-secret", "--json"],
    )

    # Then: both commands return structured JSON and do not leak secret-like input.
    assert happy.exit_code == 0, happy.stdout
    assert blocks.exit_code == 0, blocks.stdout
    happy_payload = json.loads(happy.stdout)
    block_payload = json.loads(blocks.stdout)
    assert happy_payload["scenario_id"] == "C001"
    assert block_payload["scenario_id"] == "C002"
    assert happy_payload["openai_compatible_provider"] == "selected"
    assert block_payload["missing_approval"] == "blocked"
    assert "sk-wave16-cli-secret" not in blocks.stdout


def test_wave16_eval_reports_provider_http_suite_without_production_claim() -> None:
    # Given: Wave16 provider live HTTP happy and adversarial scenarios.
    payload = run_wave16_eval()

    # When / Then: the eval summarizes governance and no-production-claim status.
    assert payload["suite"] == "wave16"
    assert payload["failed"] == 0
    assert payload["provider_http_happy_passed"] is True
    assert payload["provider_http_blocks_passed"] is True
    assert payload["live_production_claimed"] is False
