from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_wave4_connectors_cli_reports_expected_lifecycle_payload() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["wave4-connectors", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["lifecycle_report"] == {
        "mcp-conn": "healthy",
        "api-conn": "unhealthy",
        "plugin-conn": "disabled",
        "registered-conn": "registered",
    }
    assert payload["discovered_tool_names"] == [
        "api.fetch",
        "mcp.echo",
        "plugin.sync",
        "registered.scan",
    ]
    assert payload["model_visible_tools"] == ["mcp.echo"]
    assert payload["healthy_dispatch"]["decision"] == "allowed"
    assert payload["healthy_dispatch"]["result"]["capability_id"] == "mcp.echo"
    assert payload["unhealthy_dispatch"]["decision"] == "blocked"
    assert payload["unhealthy_dispatch"]["reason"] == "capability_not_model_visible"


def test_wave4_workflow_cli_redacts_secret_like_value_and_returns_structured_surfaces() -> None:
    runner = CliRunner()
    raw_secret = "ghp_TEST_FIXTURE"
    result = runner.invoke(
        app,
        [
            "wave4-workflow",
            "--secret-like",
            raw_secret,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["no_secret_echo"] is True
    assert raw_secret not in serialized
    assert payload["credential"]["credential_scopes"] == ["external.openai.readonly"]
    assert payload["workflow_job"]["principal_id"] == "principal-wave4"
    assert payload["workflow_job"]["session_id"] == "session-wave4"
    assert payload["workflow_job"]["job_id"] == "job-wave4-001"
    assert payload["workflow_job"]["idempotency_key"] == "idem-wave4-001"
    assert payload["retry_job"]["status"] == "retry_pending"
    assert payload["retry_job"]["attempt"] == 1
    assert payload["gateway_draft"]["draft_only"] is True
    assert payload["cron_draft"]["draft_only"] is True
    assert payload["gateway_draft"]["side_effects"] is False
    assert payload["cron_draft"]["side_effects"] is False


def test_wave4_eval_cli_reports_wave4_suite() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["wave4-eval", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "wave4"
    assert payload["total"] == 6
    assert payload["passed"] == 6
    assert payload["failed"] == 0
