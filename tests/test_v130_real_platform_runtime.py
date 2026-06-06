from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.real_platform_runtime import build_real_platform_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v130_release_gate_reports_gateway_api_session_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.3.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.3.0"
    assert payload["release_stage"] == "gateway_api_session_platform"
    assert payload["gateway_api_session_platform_contract_available"] is True
    assert payload["api_dry_run_available"] is True
    assert payload["gateway_session_smoke_available"] is True
    assert payload["session_store_export_available"] is True
    assert payload["acp_batch_smoke_available"] is True
    assert payload["real_platform_runtime_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v1.4.0"
    assert "real_platform_runtime_gateway_loopback_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_real_platform_status_reports_surfaces_without_starting_handlers() -> None:
    result = build_real_platform_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.3.0"
    assert payload["objective_contract_id"] == "zeus.v1.3.0.gateway_api_session_platform"
    assert payload["api_runtime_available"] is True
    assert payload["gateway_runtime_available"] is True
    assert payload["session_store_available"] is True
    assert payload["acp_adapter_available"] is True
    assert payload["batch_runner_available"] is True
    assert payload["server_started"] is False
    assert payload["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_real_platform_api_dry_run_reports_routes_without_server_start() -> None:
    result = build_real_platform_contract(scenario="api-dry-run")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["api_dry_run_ready"] is True
    assert "/v1/chat/completions" in payload["api_routes"]
    assert "/v1/responses" in payload["api_routes"]
    assert payload["server_started"] is False
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False


def test_real_platform_gateway_loopback_smoke_persists_and_replays_session() -> None:
    result = build_real_platform_contract(scenario="gateway-loopback-smoke")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["gateway_loopback_ready"] is True
    assert payload["gateway_decision"] == "allowed"
    assert payload["gateway_reason"] == "allowed"
    assert payload["gateway_session_count"] == 1
    assert payload["gateway_audit_records"] >= 2
    assert payload["idempotency_replay_stable"] is True
    assert payload["cleanup_performed"] is True
    assert payload["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["no_secret_echo"] is True


def test_real_platform_blocks_external_gateway_delivery() -> None:
    result = build_real_platform_contract(scenario="gateway-blocked-external")
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "external_delivery_blocked" in payload["blocked_reasons"]
    assert payload["gateway_reason"] == "external_delivery_blocked"
    assert payload["external_delivery_opened"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_platform_session_secret_boundary_redacts_export() -> None:
    result = build_real_platform_contract(scenario="session-secret-boundary")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "report"
    assert payload["session_store_ready"] is True
    assert payload["session_export_ready"] is True
    assert payload["cleanup_performed"] is True
    assert "api_key=abc123" not in serialized
    assert payload["raw_secret_returned"] is False
    assert payload["no_secret_echo"] is True


def test_real_platform_batch_acp_smoke_reports_adapter_readiness() -> None:
    result = build_real_platform_contract(scenario="batch-acp-smoke")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["batch_runner_ready"] is True
    assert payload["acp_adapter_ready"] is True
    assert payload["batch_compiled_count"] >= 1
    assert payload["acp_method"] == "zeus.objective.compile"
    assert payload["server_started"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_platform_cli_and_library_match() -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        ["platform-runtime", "--scenario", "gateway-loopback-smoke", "--json"],
    )
    library_payload = ZeusAgent().platform_runtime(scenario="gateway-loopback-smoke")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["gateway_loopback_ready"] is True
    assert library_payload["gateway_loopback_ready"] is True
    assert cli_payload["gateway_decision"] == library_payload["gateway_decision"]
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
