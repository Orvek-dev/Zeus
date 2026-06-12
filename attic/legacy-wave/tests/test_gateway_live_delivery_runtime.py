from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.gateway_live_delivery_runtime import build_gateway_live_delivery_contract
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v100rc4_release_gate_reports_gateway_live_delivery_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.4")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.4"
    assert payload["release_stage"] == "gateway_live_delivery"
    assert payload["gateway_live_delivery_contract_available"] is True
    assert payload["gateway_settings_available"] is True
    assert payload["gateway_pairing_available"] is True
    assert payload["gateway_delivery_envelope_available"] is True
    assert payload["gateway_delivery_body_available"] is True
    assert payload["gateway_loopback_http_available"] is True
    assert payload["gateway_external_delivery_available"] is False
    assert payload["gateway_webhook_available"] is False
    assert payload["gateway_live_delivery_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v1.0.0-rc.5"
    assert "gateway_live_delivery_loopback_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_gateway_live_delivery_status_reports_contract_without_side_effects() -> None:
    result = build_gateway_live_delivery_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.4"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.4.gateway_live_delivery"
    assert payload["scenario"] == "status"
    assert payload["gateway_external_delivery_available"] is False
    assert payload["gateway_webhook_available"] is False
    assert payload["gateway_live_delivery_ready"] is False
    assert payload["network_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["handler_executed"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["no_secret_echo"] is True


def test_gateway_live_delivery_loopback_smoke_executes_with_pairing_audit_and_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    material = "gateway-" + "rc4-token-value"
    monkeypatch.setenv("ZEUS_RC4_GATEWAY_TOKEN", material)

    result = build_gateway_live_delivery_contract(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC4_GATEWAY_TOKEN",
        target="slack://ops",
        message="Zeus gateway live delivery checkpoint",
        home=tmp_path,
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "report"
    assert payload["gateway_live_delivery_ready"] is True
    assert payload["production_ready"] is False
    assert payload["gateway_external_delivery_available"] is False
    assert payload["gateway_smoke"]["settings"]["decision"] == "configured"
    assert payload["gateway_smoke"]["pairing"]["decision"] == "paired"
    assert payload["gateway_smoke"]["delivery_envelope"]["decision"] == "prepared"
    assert payload["gateway_smoke"]["delivery_body"]["decision"] == "materialized"
    assert payload["gateway_smoke"]["loopback_execution"]["decision"] == "executed"
    assert payload["gateway_smoke"]["http_execution"]["decision"] == "executed"
    assert payload["gateway_smoke"]["http_execution"]["local_http_loopback"] is True
    assert payload["gateway_smoke"]["http_execution"]["non_loopback_network_opened"] is False
    assert payload["gateway_smoke"]["audit"]["decision"] == "audit_ready"
    assert payload["gateway_smoke"]["redaction"]["decision"] == "redacted"
    assert payload["gateway_smoke"]["server_request_count"] == 1
    assert payload["gateway_smoke"]["server_shutdown_complete"] is True
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["credential_material_accessed"] is True
    assert payload["external_delivery_opened"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True
    assert material not in serialized


def test_gateway_live_delivery_blocks_missing_secret_before_loopback_network(tmp_path: Path) -> None:
    result = build_gateway_live_delivery_contract(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC4_MISSING_GATEWAY_TOKEN",
        target="slack://ops",
        home=tmp_path,
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "secret_material_missing" in payload["blocked_reasons"]
    assert payload["gateway_live_delivery_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["no_secret_echo"] is True


def test_gateway_live_delivery_blocks_unallowlisted_target_without_network(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ZEUS_RC4_GATEWAY_TOKEN", "gateway-" + "rc4-token-value")

    result = build_gateway_live_delivery_contract(
        scenario="blocked-target",
        secret_ref="env://ZEUS_RC4_GATEWAY_TOKEN",
        target="discord://ops",
        home=tmp_path,
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "delivery_target_not_allowlisted" in payload["blocked_reasons"]
    assert payload["gateway_live_delivery_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert "secret_material" not in payload["gateway_smoke"]
    assert payload["no_secret_echo"] is True


def test_gateway_live_delivery_cli_and_library_match(tmp_path: Path, monkeypatch) -> None:
    material = "gateway-" + "rc4-token-value"
    monkeypatch.setenv("ZEUS_RC4_GATEWAY_TOKEN", material)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "gateway-live-delivery",
            "--scenario",
            "loopback-smoke",
            "--secret-ref",
            "env://ZEUS_RC4_GATEWAY_TOKEN",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).gateway_live_delivery(
        scenario="loopback-smoke",
        secret_ref="env://ZEUS_RC4_GATEWAY_TOKEN",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["gateway_live_delivery_ready"] is True
    assert library_payload["gateway_live_delivery_ready"] is True
    assert cli_payload["gateway_external_delivery_available"] is False
    assert material not in completed.stdout
    assert material not in json.dumps(library_payload)
