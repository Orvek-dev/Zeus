from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.real_product_platform_runtime import build_real_product_platform_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v170_release_gate_reports_product_platform_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.7.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.7.0"
    assert payload["release_stage"] == "product_ux_platform_status"
    assert payload["real_product_platform_contract_available"] is True
    assert payload["persona_surface_available"] is True
    assert payload["platform_cockpit_available"] is True
    assert payload["live_status_surface_available"] is True
    assert payload["operator_command_map_available"] is True
    assert payload["public_boundary_report_available"] is True
    assert payload["product_platform_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] is None
    assert "product_platform_status_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_real_product_platform_status_aggregates_user_facing_surfaces(tmp_path: Path) -> None:
    result = build_real_product_platform_contract(scenario="status", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.7.0"
    assert payload["objective_contract_id"] == "zeus.v1.7.0.product_ux_platform_status"
    assert payload["status_surface_count"] >= 6
    assert payload["zeus_call_response"] == "Zeus is here."
    assert payload["zeus_korean_call_response"] == "네, Zeus입니다."
    assert payload["persona_contract"]["decision"] == "report"
    assert payload["platform_contract"]["decision"] == "report"
    assert payload["live_cockpit_contract"]["decision"] == "report"
    assert payload["product_platform_ready"] is True
    assert payload["production_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True


def test_real_product_platform_persona_smoke_selects_work_profile(tmp_path: Path) -> None:
    result = build_real_product_platform_contract(scenario="persona-smoke", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["persona_surface_ready"] is True
    assert payload["persona_contract"]["selected_profile"]["profile"] == "work"
    assert payload["persona_contract"]["selected_profile"]["objective_mode_active"] is True
    assert payload["chat_turn_started"] is False
    assert payload["authority_widened"] is False
    assert payload["no_secret_echo"] is True


def test_real_product_platform_platform_cockpit_smoke_keeps_api_dry() -> None:
    result = build_real_product_platform_contract(scenario="platform-cockpit-smoke")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["platform_status_ready"] is True
    assert payload["platform_contract"]["selected_surface"]["surface_id"] == "api"
    assert payload["platform_contract"]["api_server_started"] is False
    assert payload["platform_contract"]["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_product_platform_live_status_smoke_does_not_open_transport(tmp_path: Path) -> None:
    result = build_real_product_platform_contract(scenario="live-status-smoke", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["live_status_ready"] is True
    assert payload["live_cockpit_contract"]["decision"] == "report"
    assert payload["live_cockpit_contract"]["approval_required"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_real_product_platform_operator_command_map_is_actionable() -> None:
    result = build_real_product_platform_contract(scenario="operator-command-map")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["operator_command_map_ready"] is True
    assert payload["operator_command_count"] >= 6
    assert "zeus persona --profile work --json" in payload["operator_commands"]
    assert "zeus product-platform-runtime --scenario live-status-smoke --json" in payload["operator_commands"]
    assert payload["handler_executed"] is False
    assert payload["no_secret_echo"] is True


def test_real_product_platform_public_boundary_blocks_production_claims(tmp_path: Path) -> None:
    result = build_real_product_platform_contract(scenario="public-boundary", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert payload["public_boundary_ready"] is True
    assert "production_live_execution_not_enabled" in payload["blocked_reasons"]
    assert payload["production_ready"] is False
    assert payload["live_production_claimed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True


def test_real_product_platform_secret_marker_is_blocked_without_echo(tmp_path: Path) -> None:
    result = build_real_product_platform_contract(
        scenario="status",
        home=tmp_path,
        operator_note="platform status with sk-v170-product-secret",
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert "sk-v170-product-secret" not in serialized
    assert payload["raw_secret_returned"] is False
    assert payload["no_secret_echo"] is True


def test_real_product_platform_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "product-platform-runtime",
            "--home",
            str(tmp_path),
            "--scenario",
            "operator-command-map",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).product_platform_runtime(
        scenario="operator-command-map",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["operator_command_map_ready"] is True
    assert library_payload["operator_command_map_ready"] is True
    assert cli_payload["production_ready"] is False
    assert library_payload["production_ready"] is False
