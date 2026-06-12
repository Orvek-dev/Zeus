from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.higher_order_agent_os_runtime import build_higher_order_agent_os
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v600_release_gate_reports_higher_order_agent_os_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v6.0.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v6.0.0"
    assert payload["release_stage"] == "higher_order_zeus_agent_os"
    assert payload["higher_order_agent_os_available"] is True
    assert payload["zeus_tui_cockpit_available"] is True
    assert payload["recursive_improvement_review_available"] is True
    assert payload["plugin_ecosystem_skeleton_available"] is True
    assert payload["remote_sandbox_contract_available"] is True
    assert payload["tenant_auth_contract_available"] is True
    assert payload["higher_order_agent_os_ready"] is True
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v6.1.0"


def test_higher_order_agent_os_status_aggregates_objective_and_connector_surfaces(tmp_path: Path) -> None:
    payload = build_higher_order_agent_os(home=tmp_path, scenario="status").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v6.0.0"
    assert payload["zeus_call_response"] == "네, 제우스입니다."
    assert payload["objective_compiler_workflow_ready"] is True
    assert payload["governed_live_connector_platform_ready"] is True
    assert payload["tui_cockpit_ready"] is True
    assert payload["recursive_improvement_review_ready"] is True
    assert payload["plugin_ecosystem_skeleton_ready"] is True
    assert payload["remote_sandbox_contract_ready"] is True
    assert payload["tenant_auth_contract_ready"] is True
    assert payload["higher_order_agent_os_ready"] is True
    assert payload["production_ready"] is False
    assert payload["network_opened"] is False


def test_higher_order_agent_os_operator_cockpit_exposes_useful_commands(tmp_path: Path) -> None:
    payload = build_higher_order_agent_os(home=tmp_path, scenario="operator-cockpit").to_payload()

    assert payload["decision"] == "report"
    assert any("zeus objective-compile-workflow" in command for command in payload["operator_commands"])
    assert any("zeus governed-live-connectors" in command for command in payload["operator_commands"])
    assert any("zeus higher-order-agent-os" in command for command in payload["operator_commands"])
    assert payload["tui_panels"] == [
        "objective",
        "workflow",
        "authority",
        "connectors",
        "evidence",
        "learning",
        "security",
    ]
    assert payload["handler_executed"] is False


def test_higher_order_agent_os_public_boundary_blocks_unrestricted_production_claim(tmp_path: Path) -> None:
    payload = build_higher_order_agent_os(home=tmp_path, scenario="public-boundary").to_payload()

    assert payload["decision"] == "blocked"
    assert "production_live_execution_not_enabled" in payload["blocked_reasons"]
    assert "unattended_execution_not_enabled" in payload["blocked_reasons"]
    assert payload["production_ready"] is False
    assert payload["remote_sandbox_enabled"] is False
    assert payload["multi_user_hosted_enabled"] is False
    assert payload["memory_auto_promotion"] is False


def test_cli_and_library_expose_higher_order_agent_os(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        [
            "higher-order-agent-os",
            "--scenario",
            "status",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).higher_order_agent_os(scenario="status")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == "v6.0.0"
    assert library_payload["target_version"] == "v6.0.0"
    assert cli_payload["higher_order_agent_os_ready"] is True
    assert library_payload["higher_order_agent_os_ready"] is True
