from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_wave7_registry_cli_reports_manifest_and_probe_state() -> None:
    # Given: the Wave7 registry CLI surface.
    runner = CliRunner()

    # When: the registry scenario runs.
    result = runner.invoke(app, ["wave7-registry", "--json"])

    # Then: provider/MCP/API/plugin manifests and probes are reported.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["sandbox_probe_count"] == 4
    assert payload["live_transport"] is False
    assert payload["health"]["api.partner.fetch"] == "unhealthy"
    assert payload["no_external_side_effects"] is True
    assert payload["no_secret_echo"] is True


def test_wave7_policy_cli_reports_fail_closed_blocks() -> None:
    # Given: the Wave7 policy CLI surface.
    runner = CliRunner()
    raw_secret = "ghp_TEST_FIXTURE"

    # When: policy-block checks run.
    result = runner.invoke(
        app,
        ["wave7-policy", "--secret-like", raw_secret, "--json"],
    )

    # Then: unsafe paths are blocked without echoing the raw secret.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["duplicate_transport_id"] == "blocked"
    assert payload["live_enablement_without_promotion"] == "blocked"
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in result.stdout


def test_wave7_eval_cli_reports_registry_policy_and_wave6_compatibility() -> None:
    # Given: the Wave7 evaluation CLI surface.
    runner = CliRunner()

    # When: the Wave7 eval suite runs.
    result = runner.invoke(app, ["wave7-eval", "--json"])

    # Then: registry, policy, and upstream compatibility checks pass.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "wave7"
    assert payload["total"] == 7
    assert payload["passed"] == 7
    assert payload["failed"] == 0
