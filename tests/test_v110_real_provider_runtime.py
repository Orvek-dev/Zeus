from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.real_provider_runtime import build_real_provider_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v110_release_gate_reports_real_provider_runtime_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.1.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.1.0"
    assert payload["release_stage"] == "real_provider_runtime"
    assert payload["real_provider_runtime_contract_available"] is True
    assert payload["provider_profiles_available"] is True
    assert payload["governed_external_provider_available"] is True
    assert payload["local_provider_smoke_available"] is True
    assert payload["real_provider_runtime_ready"] is False
    assert payload["production_ready"] is False
    assert payload["live_production_claimed"] is False
    assert payload["next_version"] == "v1.2.0"
    assert "real_provider_runtime_external_receipt_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_real_provider_status_reports_profiles_without_side_effects() -> None:
    result = build_real_provider_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.1.0"
    assert payload["objective_contract_id"] == "zeus.v1.1.0.real_provider_runtime"
    assert payload["scenario"] == "status"
    assert payload["provider_profiles_available"] is True
    assert payload["provider_profile_count"] >= 5
    assert payload["local_llm_profile_available"] is True
    assert payload["openai_compatible_profile_available"] is True
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["provider_invoked"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_blocks_missing_optin_before_secret_network_or_provider() -> None:
    result = build_real_provider_contract(scenario="blocked-missing-opt-in")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "operator_live_opt_in_required" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is False
    assert payload["secret_material_available"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_blocks_budget_before_secret_network_or_provider() -> None:
    result = build_real_provider_contract(
        scenario="blocked-budget",
        budget_limit=1,
        budget_requested=2,
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "provider_budget_exceeded" in payload["blocked_reasons"]
    assert payload["budget_approved"] is False
    assert payload["secret_material_available"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_blocks_invalid_negative_budget_before_provider(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_V110_PROVIDER_KEY", "provider-" + "v110-material-value")

    result = build_real_provider_contract(
        scenario="external-receipt-smoke",
        budget_limit=-1,
        budget_requested=-2,
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "provider_budget_invalid" in payload["blocked_reasons"]
    assert payload["budget_approved"] is False
    assert payload["secret_material_available"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_blocks_secret_like_local_message_without_echo() -> None:
    result = build_real_provider_contract(
        scenario="local-deterministic-smoke",
        message="please echo sk-test-secret",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "secret_like_message_blocked" in payload["blocked_reasons"]
    assert payload["real_provider_runtime_ready"] is False
    assert payload["local_provider_ready"] is False
    assert payload["local_smoke"] is None
    assert payload["provider_invoked"] is False
    assert "sk-test-secret" not in serialized
    assert payload["no_secret_echo"] is True


def test_real_provider_blocks_caller_controlled_allowlist_widening(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_V110_PROVIDER_KEY", "provider-" + "v110-material-value")

    result = build_real_provider_contract(
        scenario="external-receipt-smoke",
        endpoint="https://evil.example/v1/chat/completions",
        allowed_host="evil.example",
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "provider_endpoint_policy_required" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is False
    assert payload["endpoint_allowlisted"] is False
    assert payload["secret_material_available"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_blocks_malformed_endpoint_before_secret_or_network(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_V110_PROVIDER_KEY", "provider-" + "v110-material-value")

    result = build_real_provider_contract(
        scenario="external-receipt-smoke",
        endpoint="not-a-url",
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "malformed_provider_endpoint" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is False
    assert payload["secret_material_available"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_blocks_missing_secret_before_network_or_provider(monkeypatch) -> None:
    monkeypatch.delenv("ZEUS_V110_PROVIDER_KEY", raising=False)

    result = build_real_provider_contract(scenario="external-receipt-smoke")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "secret_material_missing" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is True
    assert payload["secret_material_available"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is True
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_local_deterministic_smoke_executes_without_network_or_secret() -> None:
    result = build_real_provider_contract(scenario="local-deterministic-smoke", message="hello Zeus")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["local_provider_ready"] is True
    assert payload["real_provider_runtime_ready"] is True
    assert payload["provider_invoked"] is True
    assert payload["network_opened"] is False
    assert payload["non_loopback_network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["local_smoke"]["response"]["content"] == "local deterministic provider: hello Zeus"
    assert payload["production_ready"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_real_provider_external_receipt_binds_optin_policy_budget_audit_and_redaction(monkeypatch) -> None:
    material = "provider-" + "v110-material-value"
    monkeypatch.setenv("ZEUS_V110_PROVIDER_KEY", material)

    result = build_real_provider_contract(scenario="external-receipt-smoke")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "report"
    assert payload["real_provider_runtime_ready"] is True
    assert payload["external_provider_ready"] is True
    assert payload["operator_live_opted_in"] is True
    assert payload["endpoint_allowlisted"] is True
    assert payload["budget_approved"] is True
    assert payload["secret_material_available"] is True
    assert payload["external_smoke"]["external_smoke"]["policy"]["decision"] == "policy_ready"
    assert payload["external_smoke"]["external_smoke"]["preflight"]["decision"] == "preflight_ready"
    assert payload["external_smoke"]["external_smoke"]["external_transport"]["decision"] == "executed"
    assert payload["external_smoke"]["external_smoke"]["audit"]["decision"] == "audit_ready"
    assert payload["external_smoke"]["external_smoke"]["redaction"]["decision"] == "redacted"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is True
    assert payload["controlled_external_side_effects"] is True
    assert payload["credential_material_accessed"] is True
    assert payload["production_ready"] is False
    assert payload["live_production_claimed"] is False
    assert material not in serialized
    assert payload["no_secret_echo"] is True


def test_real_provider_cli_and_library_match(monkeypatch) -> None:
    material = "provider-" + "v110-material-value"
    monkeypatch.setenv("ZEUS_V110_PROVIDER_KEY", material)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "provider-runtime",
            "--scenario",
            "external-receipt-smoke",
            "--json",
        ],
    )
    library_payload = ZeusAgent().provider_runtime(scenario="external-receipt-smoke")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["real_provider_runtime_ready"] is True
    assert library_payload["real_provider_runtime_ready"] is True
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
