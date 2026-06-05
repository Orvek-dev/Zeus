from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.provider_live_api_runtime import build_provider_live_api_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v100rc2_release_gate_reports_provider_live_api_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.2")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.2"
    assert payload["release_stage"] == "provider_live_api"
    assert payload["provider_live_api_contract_available"] is True
    assert payload["provider_loopback_http_available"] is True
    assert payload["provider_credentialed_http_available"] is True
    assert payload["provider_external_transport_available"] is False
    assert payload["provider_direct_adapter_available"] is True
    assert payload["provider_live_api_ready"] is False
    assert payload["production_ready"] is False
    assert "provider_live_api_loopback_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_provider_live_api_status_reports_contract_without_side_effects() -> None:
    result = build_provider_live_api_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.2"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.2.provider_live_api"
    assert payload["scenario"] == "status"
    assert payload["provider_live_api_contract_available"] is True
    assert payload["provider_external_transport_available"] is False
    assert payload["provider_live_api_ready"] is False
    assert payload["production_ready"] is False
    assert payload["network_opened"] is False
    assert payload["non_loopback_network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_provider_live_api_loopback_smoke_executes_with_audit_and_cleanup(monkeypatch) -> None:
    material = "provider-" + "rc2-material-value"
    monkeypatch.setenv("ZEUS_RC2_PROVIDER_KEY", material)

    result = build_provider_live_api_contract(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC2_PROVIDER_KEY",
        message="summarize provider live api checkpoint",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "report"
    assert payload["scenario"] == "loopback-smoke"
    assert payload["provider_live_api_ready"] is True
    assert payload["production_ready"] is False
    assert payload["loopback_smoke"]["execution"]["decision"] == "executed"
    assert payload["loopback_smoke"]["execution"]["provider_invoked"] is True
    assert payload["loopback_smoke"]["execution"]["local_http_loopback"] is True
    assert payload["loopback_smoke"]["audit"]["decision"] == "audit_ready"
    assert payload["loopback_smoke"]["redaction"]["decision"] == "redacted"
    assert payload["loopback_smoke"]["server_shutdown_complete"] is True
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["credential_material_accessed"] is True
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True
    assert material not in serialized


def test_provider_live_api_blocks_missing_secret_before_loopback_network() -> None:
    result = build_provider_live_api_contract(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC2_MISSING_PROVIDER_KEY",
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "secret_material_missing" in payload["blocked_reasons"]
    assert payload["provider_live_api_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_provider_live_api_cli_and_library_match(monkeypatch) -> None:
    material = "provider-" + "rc2-material-value"
    monkeypatch.setenv("ZEUS_RC2_PROVIDER_KEY", material)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "provider-live-api",
            "--scenario",
            "loopback-smoke",
            "--secret-ref",
            "env://ZEUS_RC2_PROVIDER_KEY",
            "--json",
        ],
    )
    library_payload = ZeusAgent().provider_live_api(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC2_PROVIDER_KEY",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["provider_live_api_ready"] is True
    assert library_payload["provider_live_api_ready"] is True
    assert material not in completed.stdout
    assert material not in json.dumps(library_payload)
