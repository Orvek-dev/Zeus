from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime.agent import ZeusAgent
from zeus_agent.production_scale_platform_runtime import build_production_scale_platform_contract
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v240_release_gate_reports_production_scale_checkpoint() -> None:
    result = build_release_gated_ulw_status(target_version="v2.4.0")
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v2.4.0"
    assert payload["release_stage"] == "production_scale_platform"
    assert payload["production_scale_platform_contract_available"] is True
    assert payload["plugin_ecosystem_available"] is True
    assert payload["remote_sandbox_backend_interface_available"] is True
    assert payload["tenant_model_available"] is True
    assert payload["candidate_only_learning_available"] is True
    assert payload["production_scale_platform_ready"] is False
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v3.0.0"


def test_status_reports_scale_platform_without_live_side_effects(tmp_path: Path) -> None:
    result = build_production_scale_platform_contract(scenario="status", home=tmp_path)
    payload = result.to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v2.4.0"
    assert payload["production_scale_platform_ready"] is True
    assert payload["production_ready"] is False
    assert payload["plugin_quarantine_available"] is True
    assert payload["network_egress_default_denied"] is True
    assert payload["credential_passthrough_default_denied"] is True
    assert payload["tenant_isolation_contract_available"] is True
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False


def test_plugin_ecosystem_keeps_valid_plugin_quarantined() -> None:
    payload = build_production_scale_platform_contract(scenario="plugin-ecosystem").to_payload()

    assert payload["decision"] == "report"
    assert payload["plugin_ecosystem_contract"]["decision"] == "quarantined"
    assert payload["plugin_ecosystem_contract"]["tool_registration_allowed"] is False
    assert payload["active_rule_written"] is False
    assert payload["handler_executed"] is False


def test_remote_sandbox_policy_stays_default_denied() -> None:
    payload = build_production_scale_platform_contract(scenario="remote-sandbox-policy").to_payload()

    assert payload["decision"] == "blocked"
    assert "remote_sandbox_default_denied" in payload["blocked_reasons"]
    assert payload["remote_sandbox_policy_contract"]["network_egress_policy"] == "deny_by_default"
    assert payload["remote_sandbox_execution_opened"] is False
    assert payload["network_opened"] is False


def test_tenant_auth_and_learning_ops_are_contracts_not_execution() -> None:
    auth = build_production_scale_platform_contract(scenario="tenant-auth-contract").to_payload()
    learning = build_production_scale_platform_contract(scenario="learning-ops").to_payload()

    assert auth["decision"] == "report"
    assert auth["tenant_auth_contract"]["tenant_isolation"] == "default_deny_cross_tenant"
    assert auth["authority_widened"] is False
    assert learning["decision"] == "report"
    assert learning["learning_ops_contract"]["promotion_review"] == "required"
    assert learning["learning_ops_contract"]["automatic_rule_promotion"] is False


def test_cli_and_library_expose_production_scale_platform(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        ["production-scale-platform", "--home", str(tmp_path), "--scenario", "status", "--json"],
    )
    cli_payload = json.loads(completed.stdout)
    library_payload = ZeusAgent(home=tmp_path).production_scale_platform_runtime(scenario="status")

    assert completed.exit_code == 0
    assert cli_payload["target_version"] == "v2.4.0"
    assert cli_payload["production_scale_platform_ready"] is True
    assert library_payload["target_version"] == "v2.4.0"
    assert library_payload["production_scale_platform_ready"] is True
