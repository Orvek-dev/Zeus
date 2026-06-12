from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.model_runtime.interfaces import ProviderRuntimeResponse, ProviderUsage
from zeus_agent.wave10_provider_support import pre_adapter_blocked_adapter_invoked


def test_wave10_provider_cli_reports_runtime_lease_provider_absorption() -> None:
    # Given: the Wave10 provider absorption CLI surface.
    runner = CliRunner()

    # When: the happy provider scenario runs.
    result = runner.invoke(app, ["wave10-provider", "--json"])

    # Then: provider metadata is compiled behind RuntimeLease without side effects.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["scenario_id"] == "C001"
    assert payload["provider_contract_compiled"] is True
    assert payload["fake_provider"] == "selected"
    assert payload["local_llm_provider"] == "selected"
    assert payload["openai_compatible_provider"] == "dry_run"
    assert payload["anthropic_metadata_provider"] == "dry_run"
    assert payload["openai_arguments_json"] is True
    assert payload["tool_call_id_recorded"] is True
    assert payload["anthropic_tool_use_metadata"] is True
    assert payload["local_endpoint_metadata"] is True
    assert payload["usage_budget_recorded"] is True
    assert payload["fallback_route_recorded"] is True
    assert payload["runtime_lease_validated"] is True
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["sdk_imported"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["no_secret_echo"] is True


def test_wave10_blocks_cli_reports_fail_closed_provider_labels_without_secret_echo() -> None:
    # Given: the Wave10 provider block CLI and a secret-like sample.
    runner = CliRunner()
    raw_secret = "sk-wave10-secret-value"

    # When: block checks run.
    result = runner.invoke(
        app,
        ["wave10-blocks", "--secret-like", raw_secret, "--json"],
    )

    # Then: every unsafe provider path blocks before adapters, clients, or network.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["scenario_id"] == "C002"
    assert payload["missing_runtime_lease"] == "blocked"
    assert payload["malformed_runtime_lease"] == "blocked"
    assert payload["expired_runtime_lease"] == "blocked"
    assert payload["runtime_kind_capability_mismatch"] == "blocked"
    assert payload["missing_credential_scope"] == "blocked"
    assert payload["unsafe_credential"] == "blocked"
    assert payload["live_network_without_scope"] == "blocked"
    assert payload["metadata_authority_bypass"] == "blocked"
    assert payload["fallback_after_block"] == "blocked"
    assert payload["unknown_provider"] == "blocked"
    assert payload["unknown_provider_reason"] == "unsupported_provider"
    assert payload["malformed_tool_arguments"] == "blocked"
    assert payload["malformed_tool_arguments_reason"] == "malformed_tool_arguments"
    assert payload["over_budget"] == "blocked"
    assert payload["handler_executed"] is False
    assert payload["adapter_invoked"] is False
    assert payload["client_constructed"] is False
    assert payload["network_opened"] is False
    assert payload["sdk_imported"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["no_secret_echo"] is True
    assert payload["raw_secret_present"] is False
    assert raw_secret not in result.stdout


def test_wave10_eval_cli_reports_provider_absorption_suite() -> None:
    # Given: the Wave10 evaluation CLI surface.
    runner = CliRunner()

    # When: the Wave10 eval suite runs.
    result = runner.invoke(app, ["wave10-eval", "--json"])

    # Then: the Wave10 suite reports deterministic totals and all checks pass.
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["suite"] == "wave10"
    assert payload["total"] == 8
    assert payload["passed"] == 8
    assert payload["failed"] == 0


def test_wave10_pre_adapter_blocked_invocation_is_not_inferred_from_content() -> None:
    # Given: a blocked response that would be misleading if content were treated as invocation.
    blocked = ProviderRuntimeResponse(
        decision="blocked",
        provider_kind="fake",
        provider_id="fake.provider",
        model_id="fake.model",
        response_id="resp_blocked_with_content",
        content="nonempty blocked diagnostic",
        usage=ProviderUsage(input_tokens=0, output_tokens=0, budget_units=0, latency_ms=0),
    )

    # When: the Wave10 scenario classifies pre-adapter blocked provider responses.
    invoked = pre_adapter_blocked_adapter_invoked((blocked,))

    # Then: content shape cannot turn a pre-adapter policy block into adapter execution.
    assert invoked is False
