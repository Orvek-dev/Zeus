from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_wave8_state_cli_reports_persistent_transport_registry(tmp_path) -> None:
    # Given: the Wave8 state CLI surface.
    runner = CliRunner()

    # When: transport state is generated into an isolated home.
    result = runner.invoke(app, ["wave8-state", "--home", str(tmp_path), "--json"])

    # Then: manifests, probes, health, evidence links, and idempotency are reported.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["transport_manifest_count"] == 4
    assert payload["transport_probe_count"] == 4
    assert payload["evidence_link_count"] == 8
    assert payload["idempotency_replay_stable"] is True
    assert payload["live_transport"] is False
    assert payload["no_secret_echo"] is True


def test_wave8_runtime_cli_reports_registry_policy_blocks() -> None:
    # Given: the Wave8 runtime integration CLI surface.
    runner = CliRunner()
    raw_secret = "ghp_TEST_FIXTURE"

    # When: runtime integration checks run.
    result = runner.invoke(
        app,
        ["wave8-runtime", "--secret-like", raw_secret, "--json"],
    )

    # Then: the registry gate allows healthy dry-run paths and blocks unsafe paths.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["registry_gate"] == "enabled"
    assert payload["healthy_provider_allowed"] is True
    assert payload["healthy_connector_allowed"] is True
    assert payload["unknown_transport"] == "blocked"
    assert payload["unhealthy_probe"] == "blocked"
    assert payload["transport_kind_mismatch"] == "blocked"
    assert payload["live_transport_not_authorized"] == "blocked"
    assert payload["blocked_handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert raw_secret not in result.stdout


def test_wave8_eval_cli_reports_adjacent_surface_compatibility() -> None:
    # Given: the Wave8 evaluation CLI surface.
    runner = CliRunner()

    # When: the Wave8 eval suite runs.
    result = runner.invoke(app, ["wave8-eval", "--json"])

    # Then: Wave8 and adjacent Wave5/Wave6/Wave7 compatibility checks pass.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "wave8"
    assert payload["adjacent_surface_still_works"] is True
    assert payload["total"] == 8
    assert payload["passed"] == 8
    assert payload["failed"] == 0
