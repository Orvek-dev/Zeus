from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.provider_live_optin_runtime import build_provider_live_optin_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v100rc7_release_gate_reports_provider_live_optin_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.7")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.7"
    assert payload["release_stage"] == "provider_live_optin"
    assert payload["provider_live_optin_contract_available"] is True
    assert payload["provider_external_transport_available"] is True
    assert payload["provider_external_receipt_available"] is True
    assert payload["remote_transport_policy_available"] is True
    assert payload["remote_executor_preflight_available"] is True
    assert payload["provider_live_optin_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v1.0.0-rc.8"
    assert "provider_live_optin_external_receipt_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_provider_live_optin_status_reports_without_side_effects() -> None:
    result = build_provider_live_optin_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.7"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.7.provider_live_optin"
    assert payload["scenario"] == "status"
    assert payload["operator_live_opted_in"] is False
    assert payload["provider_live_optin_ready"] is False
    assert payload["network_opened"] is False
    assert payload["non_loopback_network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_provider_live_optin_blocks_missing_operator_optin_before_secret_or_network() -> None:
    result = build_provider_live_optin_contract(scenario="blocked-missing-opt-in")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "operator_live_opt_in_required" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is False
    assert payload["secret_material_available"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_provider_live_optin_blocks_unallowlisted_endpoint_before_secret_or_network() -> None:
    result = build_provider_live_optin_contract(scenario="blocked-unallowlisted")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "remote_target_not_allowlisted" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is True
    assert payload["endpoint_allowlisted"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_provider_live_optin_blocks_missing_secret_before_external_receipt(monkeypatch) -> None:
    monkeypatch.delenv("ZEUS_RC7_PROVIDER_KEY", raising=False)

    result = build_provider_live_optin_contract(scenario="blocked-missing-secret")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "secret_material_missing" in payload["blocked_reasons"]
    assert payload["operator_live_opted_in"] is True
    assert payload["endpoint_allowlisted"] is True
    assert payload["credential_material_accessed"] is True
    assert payload["network_opened"] is False
    assert payload["provider_invoked"] is False
    assert payload["no_secret_echo"] is True


def test_provider_live_optin_external_receipt_binds_policy_preflight_audit_and_redaction(monkeypatch) -> None:
    material = "provider-" + "rc7-material-value"
    monkeypatch.setenv("ZEUS_RC7_PROVIDER_KEY", material)

    result = build_provider_live_optin_contract(scenario="external-receipt-smoke")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "report"
    assert payload["provider_live_optin_ready"] is True
    assert payload["operator_live_opted_in"] is True
    assert payload["endpoint_allowlisted"] is True
    assert payload["secret_material_available"] is True
    assert payload["external_smoke"]["policy"]["decision"] == "policy_ready"
    assert payload["external_smoke"]["preflight"]["decision"] == "preflight_ready"
    assert payload["external_smoke"]["external_transport"]["decision"] == "executed"
    assert payload["external_smoke"]["audit"]["decision"] == "audit_ready"
    assert payload["external_smoke"]["redaction"]["decision"] == "redacted"
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is True
    assert payload["controlled_external_side_effects"] is True
    assert payload["credential_material_accessed"] is True
    assert payload["material_released"] is False
    assert payload["live_production_claimed"] is False
    assert material not in serialized
    assert payload["no_secret_echo"] is True


def test_provider_live_optin_cli_and_library_match(monkeypatch) -> None:
    material = "provider-" + "rc7-material-value"
    monkeypatch.setenv("ZEUS_RC7_PROVIDER_KEY", material)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "provider-live-optin",
            "--scenario",
            "external-receipt-smoke",
            "--json",
        ],
    )
    library_payload = ZeusAgent().provider_live_optin(scenario="external-receipt-smoke")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["provider_live_optin_ready"] is True
    assert library_payload["provider_live_optin_ready"] is True
    assert material not in completed.stdout
    assert material not in json.dumps(library_payload)
