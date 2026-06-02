from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_wave9_lease_cli_reports_scoped_runtime_intake() -> None:
    # Given: the Wave9 runtime lease CLI surface.
    runner = CliRunner()

    # When: the lease scenario runs.
    result = runner.invoke(app, ["wave9-lease", "--json"])

    # Then: provider/MCP/gateway/cron intake is scoped and side-effect free.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["runtime_lease_validated"] is True
    assert payload["principal_id"] == "wave9.principal.worker_a"
    assert payload["objective_id"] == "wave9.objective.runtime_lease"
    assert payload["provider_scope"] == "allowed"
    assert payload["mcp_scope"] == "allowed"
    assert payload["gateway_scope"] == "allowed"
    assert payload["cron_scope"] == "allowed"
    assert payload["api_tool_scope"] == "allowed"
    assert payload["plugin_scope"] == "allowed"
    assert payload["request_scoped_authority"] is True
    assert payload["provider_authority_network_grants"] == 0
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["live_transport_allowed"] is False
    assert payload["no_secret_echo"] is True


def test_wave9_blocks_cli_reports_fail_closed_labels_without_secret_echo() -> None:
    # Given: the Wave9 block CLI surface and a secret-like credential sample.
    runner = CliRunner()
    raw_secret = "ghp_TEST_FIXTURE"

    # When: block checks run.
    result = runner.invoke(
        app,
        ["wave9-blocks", "--secret-like", raw_secret, "--json"],
    )

    # Then: all unsafe intake classes block before handlers and omit raw secrets.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["missing_runtime_lease"] == "blocked"
    assert payload["malformed_principal"] == "blocked"
    assert payload["malformed_runtime_lease"] == "blocked"
    assert payload["runtime_kind_capability_mismatch"] == "blocked"
    assert payload["authority_widening"] == "blocked"
    assert payload["scope_escalation"] == "blocked"
    assert payload["evidence_scope_bypass"] == "blocked"
    assert payload["unsafe_credential"] == "blocked"
    assert payload["live_network_without_scope"] == "blocked"
    assert payload["expired_runtime_lease"] == "blocked"
    assert payload["over_budget"] == "blocked"
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in result.stdout


def test_wave9_eval_cli_reports_runtime_lease_suite() -> None:
    # Given: the Wave9 evaluation CLI surface.
    runner = CliRunner()

    # When: the Wave9 eval suite runs.
    result = runner.invoke(app, ["wave9-eval", "--json"])

    # Then: the Wave9 suite reports deterministic totals and all checks pass.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "wave9"
    assert payload["total"] == 8
    assert payload["passed"] == 8
    assert payload["failed"] == 0
