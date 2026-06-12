from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_wave5_providers_cli_reports_runtime_ready_contracts() -> None:
    # Given: the Wave5 provider CLI surface.
    runner = CliRunner()

    # When: provider execution contracts are inspected.
    result = runner.invoke(app, ["wave5-providers", "--json"])

    # Then: local and external dry-run envelopes are reported without secrets.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["no_raw_env_reads"] is True
    assert payload["provider_kinds"] == ["fake", "local", "external"]
    assert payload["local_route"]["decision"] == "selected"
    assert payload["local_route"]["envelope"]["provider_id"] == "local-private"
    assert payload["local_route"]["envelope"]["local_private"] is True
    assert payload["local_route"]["envelope"]["transport"] == "dry_run"
    assert payload["external_envelope"]["decision"] == "selected"
    assert payload["external_envelope"]["envelope"]["credential_scope_label"] == (
        "external.openai.readonly"
    )
    assert payload["external_envelope"]["envelope"]["network_allowed"] is True
    assert payload["external_blocked"]["decision"] == "blocked"
    assert payload["external_blocked"]["route"]["network_allowed"] is False
    assert payload["no_secret_echo"] is True
    assert "ghp_TEST_FIXTURE" not in serialized
    assert "OPENAI_API_KEY" not in serialized


def test_wave5_connectors_cli_reports_broker_mediated_execution_envelopes() -> None:
    # Given: the Wave5 connector CLI surface.
    runner = CliRunner()

    # When: connector execution contracts are inspected.
    result = runner.invoke(app, ["wave5-connectors", "--json"])

    # Then: MCP/API/plugin execution remains broker-mediated and dry-run.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["mcp_execution"]["decision"] == "allowed"
    assert payload["mcp_execution"]["handler_executed"] is True
    assert payload["mcp_execution"]["envelope"]["connector_kind"] == "mcp"
    assert payload["mcp_execution"]["envelope"]["dry_run"] is True
    assert payload["api_execution"]["decision"] == "allowed"
    assert payload["api_execution"]["envelope"]["connector_kind"] == "api"
    assert payload["api_execution"]["envelope"]["credential_scope_label"] == (
        "external.partner.readonly"
    )
    assert payload["plugin_execution"]["decision"] == "allowed"
    assert payload["plugin_execution"]["envelope"]["connector_kind"] == "plugin"
    assert payload["unhealthy_block"]["decision"] == "blocked"
    assert payload["unhealthy_block"]["handler_executed"] is False
    assert payload["unauthorized_block"]["decision"] == "blocked"
    assert payload["unauthorized_block"]["handler_executed"] is False
    assert payload["secret_block"]["decision"] == "blocked"
    assert payload["no_secret_echo"] is True
    assert "ghp_TEST_FIXTURE" not in serialized


def test_wave5_eval_cli_reports_provider_connector_suite() -> None:
    # Given: the Wave5 evaluation CLI surface.
    runner = CliRunner()

    # When: the Wave5 eval suite runs.
    result = runner.invoke(app, ["wave5-eval", "--json"])

    # Then: all provider and connector execution-contract checks pass.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "wave5"
    assert payload["total"] == 6
    assert payload["passed"] == 6
    assert payload["failed"] == 0
