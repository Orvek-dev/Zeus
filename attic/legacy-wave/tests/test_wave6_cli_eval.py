from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_wave6_state_cli_reports_persisted_runtime_counts(tmp_path) -> None:
    # Given: the Wave6 state CLI surface.
    runner = CliRunner()

    # When: runtime state is generated into an isolated home.
    result = runner.invoke(app, ["wave6-state", "--home", str(tmp_path), "--json"])

    # Then: provider and connector dry-run execution state is persisted.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["runtime_counts"]["provider_executions"] == 1
    assert payload["runtime_counts"]["connector_executions"] == 1
    assert payload["runtime_counts"]["execution_evidence_links"] == 2
    assert payload["live_transport"] is False
    assert payload["no_secret_echo"] is True


def test_wave6_promotion_cli_reports_live_transport_block(tmp_path) -> None:
    # Given: the Wave6 promotion CLI surface.
    runner = CliRunner()

    # When: live transport promotion is attempted without approval.
    result = runner.invoke(app, ["wave6-promotion", "--home", str(tmp_path), "--json"])

    # Then: promotion is blocked and persisted without side effects.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["promotion"]["decision"] == "blocked"
    assert payload["promotion"]["reason"] == "live_transport_not_authorized"
    assert payload["promotion"]["handler_executed"] is False
    assert payload["promotion"]["network_opened"] is False
    assert payload["runtime_counts"]["promotion_attempts"] == 1


def test_wave6_eval_cli_reports_state_and_promotion_suite() -> None:
    # Given: the Wave6 evaluation CLI surface.
    runner = CliRunner()

    # When: the Wave6 eval suite runs.
    result = runner.invoke(app, ["wave6-eval", "--json"])

    # Then: state and promotion checks pass.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "wave6"
    assert payload["total"] == 6
    assert payload["passed"] == 6
    assert payload["failed"] == 0
