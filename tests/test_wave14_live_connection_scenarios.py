from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.eval.wave14 import run_wave14_eval
from zeus_agent.wave14_live_connection_scenarios import (
    wave14_live_blocks_payload,
    wave14_live_plan_payload,
)


def test_wave14_live_plan_payload_plans_all_routes_without_live_execution(
    tmp_path: Path,
) -> None:
    # Given: a local Wave14 state home for a governed live-connection dry run.
    home = tmp_path / "wave14-state"

    # When: the live-connection planning scenario is built.
    payload = wave14_live_plan_payload(home=home)

    # Then: every live route is planned while execution and network stay closed.
    assert payload["scenario_id"] == "C001"
    assert payload["objective_contract_bound"] is True
    assert payload["live_connection_router_created"] is True
    assert payload["live_connection_runtime_api_available"] is True
    assert payload["decision"] == "planned"
    assert payload["route_count"] >= 5
    assert set(payload["planned_surface_kinds"]) >= {
        "provider",
        "mcp",
        "web",
        "gateway",
        "sandbox",
    }
    assert payload["dry_run"] is True
    assert payload["live_transport_allowed"] is False
    assert payload["planned_provider_route"] is True
    assert payload["planned_mcp_route"] is True
    assert payload["planned_web_route"] is True
    assert payload["planned_gateway_route"] is True
    assert payload["planned_sandbox_route"] is True
    assert payload["audit_record_created"] is True
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["raw_secret_present"] is False
    assert payload["live_production_claimed"] is False


def test_wave14_live_blocks_payload_blocks_every_unsafe_live_path_and_redacts_secret(
    tmp_path: Path,
) -> None:
    # Given: a raw secret-like value and a local Wave14 state home.
    raw_secret = "sk-wave14-block-secret"

    # When: unsafe live-connection variants are evaluated.
    payload = wave14_live_blocks_payload(
        home=tmp_path / "wave14-state",
        raw_secret=raw_secret,
    )

    # Then: each unsafe path blocks without execution, networking, or secret echo.
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["scenario_id"] == "C002"
    assert set(payload["blocked_reasons"]) >= {
        "missing_lease",
        "missing_approval",
        "credential_scope_mismatch",
        "mcp_prompt_injection",
        "web_source_unpinned",
        "sandbox_network_command_blocked",
        "plugin_quarantined",
        "gateway_target_blocked",
    }
    assert payload["missing_lease_blocked"] is True
    assert payload["missing_approval_blocked"] is True
    assert payload["credential_mismatch_blocked"] is True
    assert payload["mcp_prompt_injection_blocked"] is True
    assert payload["unpinned_web_research_blocked"] is True
    assert payload["sandbox_egress_blocked"] is True
    assert payload["plugin_quarantine_blocked"] is True
    assert payload["gateway_target_blocked"] is True
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["raw_secret_present"] is False
    assert payload["live_production_claimed"] is False
    assert raw_secret not in serialized


def test_run_wave14_eval_reports_governed_suite_and_adjacent_evals() -> None:
    # Given: the Wave14 eval runner.

    # When: the Wave14 eval suite runs in its own temporary state home.
    payload = run_wave14_eval()

    # Then: local Wave14 checks and adjacent eval smokes all pass.
    assert payload["suite"] == "wave14"
    assert payload["failed"] == 0
    assert payload["wave14_eval_total"] >= 4
    assert payload["wave14_eval_failed"] == 0
    assert payload["adjacent_surface_still_works"] is True
    assert payload["wave9_eval_passed"] is True
    assert payload["wave10_eval_passed"] is True
    assert payload["wave11_eval_passed"] is True
    assert payload["wave12_eval_passed"] is True
    assert payload["wave13_eval_passed"] is True
    assert payload["final_architecture_eval_passed"] is True
    assert payload["live_production_claimed"] is False
    assert payload["governance_gates_ok"] is True
    assert isinstance(payload["checks"], list)
    checks = {
        check["name"]: check["status"]
        for check in payload["checks"]
        if isinstance(check, dict)
    }
    assert checks["live_connection_runtime_api_available"] == "pass"
    assert checks["live_connection_route_count"] == "pass"
    assert checks["live_connection_block_reasons"] == "pass"
