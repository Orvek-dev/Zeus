from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status
from zeus_agent.sandbox_terminal_live_runtime import build_sandbox_terminal_live_contract


def test_v100rc5_release_gate_reports_sandbox_terminal_live_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v1.0.0-rc.5")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.5"
    assert payload["release_stage"] == "sandbox_terminal_live"
    assert payload["sandbox_terminal_live_contract_available"] is True
    assert payload["terminal_facade_available"] is True
    assert payload["sandbox_dispatch_facade_available"] is True
    assert payload["tool_sandbox_executor_available"] is True
    assert payload["browser_dispatch_guard_available"] is True
    assert payload["local_sandbox_execution_ready"] is False
    assert payload["remote_sandbox_available"] is False
    assert payload["docker_backend_available"] is False
    assert payload["ssh_backend_available"] is False
    assert payload["browser_live_navigation_available"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v1.0.0-rc.6"
    assert "sandbox_terminal_live_local_smoke_manual_qa" in payload["required_checkpoint_evidence"]
    assert payload["no_secret_echo"] is True


def test_sandbox_terminal_live_status_reports_contract_without_side_effects() -> None:
    result = build_sandbox_terminal_live_contract(scenario="status")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v1.0.0-rc.5"
    assert payload["objective_contract_id"] == "zeus.v1.0.0-rc.5.sandbox_terminal_live"
    assert payload["scenario"] == "status"
    assert payload["local_sandbox_execution_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["local_process_executed"] is False
    assert payload["cleanup_performed"] is False
    assert payload["remote_execution_opened"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_sandbox_terminal_live_local_smoke_executes_allowed_command_and_cleans_up(tmp_path: Path) -> None:
    result = build_sandbox_terminal_live_contract(
        scenario="local-smoke",
        command="pwd",
        home=tmp_path,
    )
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["local_sandbox_execution_ready"] is True
    assert payload["controlled_local_side_effects"] is True
    assert payload["handler_executed"] is True
    assert payload["local_process_executed"] is True
    assert payload["file_write_executed"] is False
    assert payload["network_opened"] is False
    assert payload["non_loopback_network_opened"] is False
    assert payload["remote_execution_opened"] is False
    assert payload["cleanup_performed"] is True
    assert payload["browser_guard"]["decision"] == "blocked"
    assert payload["browser_live_navigation_available"] is False
    assert payload["terminal_plan"]["decision"] == "planned"
    assert payload["sandbox_plan"]["decision"] == "planned"
    assert payload["sandbox_smoke"]["file_read"]["decision"] == "allowed"
    assert payload["sandbox_smoke"]["command_run"]["decision"] == "allowed"
    assert payload["sandbox_smoke"]["command_run"]["handler_executed"] is True
    assert payload["sandbox_smoke"]["command_run"]["evidence_record_created"] is True
    assert payload["sandbox_smoke"]["command_run"]["safe_env_used"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True


def test_sandbox_terminal_live_blocks_network_without_secret_echo_or_handler(tmp_path: Path) -> None:
    raw_secret = "sk-rc5-network-secret"
    result = build_sandbox_terminal_live_contract(
        scenario="blocked-network",
        home=tmp_path,
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "blocked"
    assert "network_command_blocked" in payload["blocked_reasons"]
    assert "network_egress_blocked" in payload["blocked_reasons"]
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["local_process_executed"] is False
    assert payload["remote_execution_opened"] is False
    assert payload["cleanup_performed"] is True
    assert payload["sandbox_smoke"]["command_run"]["decision"] == "blocked"
    assert payload["sandbox_smoke"]["command_run"]["handler_executed"] is False
    assert raw_secret not in serialized
    assert payload["no_secret_echo"] is True


def test_sandbox_terminal_live_blocks_remote_docker_ssh_and_browser_live(tmp_path: Path) -> None:
    result = build_sandbox_terminal_live_contract(
        scenario="blocked-remote",
        home=tmp_path,
    )
    payload = result.to_payload()

    assert payload["decision"] == "blocked"
    assert "backend_not_supported" in payload["blocked_reasons"]
    assert "docker_socket_mount" in payload["blocked_reasons"]
    assert "network_egress_blocked" in payload["blocked_reasons"]
    assert "resource_profile_unbounded" in payload["blocked_reasons"]
    assert "missing_cleanup_obligation" in payload["blocked_reasons"]
    assert "network_command_blocked" in payload["blocked_reasons"]
    assert "live_navigation_not_supported" in payload["blocked_reasons"]
    assert "remote_execution_not_supported" in payload["blocked_reasons"]
    assert payload["docker_backend_available"] is False
    assert payload["ssh_backend_available"] is False
    assert payload["browser_live_navigation_available"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["remote_execution_opened"] is False
    assert payload["cleanup_performed"] is True
    assert payload["no_secret_echo"] is True


def test_sandbox_terminal_live_cli_and_library_match(tmp_path: Path) -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "sandbox-terminal-live",
            "--scenario",
            "local-smoke",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).sandbox_terminal_live(scenario="local-smoke")

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["objective_contract_id"] == library_payload["objective_contract_id"]
    assert cli_payload["local_sandbox_execution_ready"] is True
    assert library_payload["local_sandbox_execution_ready"] is True
    assert cli_payload["remote_sandbox_available"] is False
    assert cli_payload["no_secret_echo"] is True
