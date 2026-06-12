from __future__ import annotations

import json
from pathlib import Path


def test_c001_loopback_payload_creates_and_resumes_local_session(tmp_path: Path) -> None:
    # Given: the G006 loopback scenario is backed by a temp local gateway DB.
    from zeus_agent.g006_gateway_scenarios import g006_gateway_loopback_payload

    # When: the scenario creates and resumes through GatewayApiRuntime.
    payload = g006_gateway_loopback_payload(db_path=tmp_path / "gateway.sqlite")

    # Then: C001 proves in-process local persistence without external delivery.
    assert payload["scenario_id"] == "C001"
    assert payload["gateway_api_runtime_created"] is True
    assert payload["session_persisted"] is True
    assert payload["resume_succeeded"] is True
    assert payload["session_id"] == "session-g006-001"
    assert payload["run_id"] == "run-g006-001"
    assert payload["goal_contract_id"] == "goal-g006-001"
    assert payload["audit_record_created"] is True
    assert payload["audit_records"] >= 2
    assert payload["gateway_session_count"] == 1
    assert payload["loopback_http_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["webhook_registered"] is False
    assert payload["standing_order_created"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False
    assert "g006-secret" not in json.dumps(payload, sort_keys=True)


def test_c002_idempotency_payload_replays_and_conflicts_without_side_effects(
    tmp_path: Path,
) -> None:
    # Given: the idempotency scenario uses one local GatewayApiRuntime store.
    from zeus_agent.g006_gateway_scenarios import g006_gateway_idempotency_payload

    # When: the same idempotency key is replayed and then conflicted.
    payload = g006_gateway_idempotency_payload(db_path=tmp_path / "gateway.sqlite")

    # Then: C002 proves stable replay and fail-closed conflict behavior.
    assert payload["scenario_id"] == "C002"
    assert payload["idempotency_replay_stable"] is True
    assert payload["replay_audit_records"] == 2
    assert payload["conflict_reason"] == "idempotency_conflict"
    assert payload["conflict_status_code"] == 409
    assert payload["gateway_session_count"] == 1
    assert payload["side_effect_count"] == 0
    assert payload["handler_executed"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["webhook_registered"] is False
    assert payload["standing_order_created"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False
    assert "g006-secret" not in json.dumps(payload, sort_keys=True)


def test_c003_fail_closed_payload_blocks_gateway_surfaces_without_secret_echo(
    tmp_path: Path,
) -> None:
    # Given: blocked GatewayApiRuntime surfaces receive raw secret-shaped input.
    from zeus_agent.g006_gateway_scenarios import g006_gateway_fail_closed_payload

    raw_secret = "sk-g006-raw-secret-do-not-echo"

    # When: the fail-closed scenario evaluates disallowed surfaces.
    payload = g006_gateway_fail_closed_payload(
        raw_secret,
        db_path=tmp_path / "gateway.sqlite",
    )

    # Then: C003 reports exact block labels without handler execution or leaks.
    assert payload["scenario_id"] == "C003"
    assert payload["unauthenticated"] == "unauthenticated"
    assert payload["non_loopback_host"] == "non_loopback_blocked"
    assert payload["webhook"] == "webhook_blocked"
    assert payload["external_delivery"] == "external_delivery_blocked"
    assert payload["standing_order"] == "standing_order_blocked"
    assert payload["handler_executed"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["webhook_registered"] is False
    assert payload["standing_order_created"] is False
    assert payload["raw_secret_present"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False
    assert raw_secret not in json.dumps(payload, sort_keys=True)


def test_g006_eval_reports_all_scenarios_passing() -> None:
    # Given: the G006 eval wraps C001, C002, and C003.
    from zeus_agent.eval.g006 import run_g006_eval

    # When: the eval suite runs in-process.
    payload = run_g006_eval()

    # Then: every G006 check passes without a live-production claim.
    assert payload["suite"] == "g006"
    assert payload["failed"] == 0
    assert payload["c001_loopback_passed"] is True
    assert payload["c002_idempotency_passed"] is True
    assert payload["c003_fail_closed_passed"] is True
    assert payload["live_production_claimed"] is False
    assert payload["checks"]
    assert all(check["status"] == "pass" for check in payload["checks"])
