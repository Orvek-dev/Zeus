from __future__ import annotations

import json
import tempfile
from pathlib import Path

from zeus_agent.g006_gateway_scenarios import (
    G006Payload,
    g006_gateway_fail_closed_payload,
    g006_gateway_idempotency_payload,
    g006_gateway_loopback_payload,
)

G006EvalValue = bool | int | str | list[dict[str, str]]
G006EvalPayload = dict[str, G006EvalValue]


def run_g006_eval() -> G006EvalPayload:
    raw_secret = "sk-g006-eval-secret"
    with tempfile.TemporaryDirectory(prefix="zeus-g006-eval-") as raw_home:
        home = Path(raw_home)
        c001 = g006_gateway_loopback_payload(db_path=home / "c001.sqlite")
        c002 = g006_gateway_idempotency_payload(db_path=home / "c002.sqlite")
        c003 = g006_gateway_fail_closed_payload(
            raw_secret,
            db_path=home / "c003.sqlite",
        )
    c001_passed = _c001_pass(c001)
    c002_passed = _c002_pass(c002)
    c003_passed = _c003_pass(c003)
    live_production_claimed = _live_production_claimed(c001, c002, c003)
    checks = [
        _check("c001_loopback", c001_passed),
        _check("c002_idempotency", c002_passed),
        _check("c003_fail_closed", c003_passed),
        _check("no_secret_echo", _no_secret_echo(raw_secret, c001, c002, c003)),
        _check("no_live_production_claim", live_production_claimed is False),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "g006",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "c001_loopback_passed": c001_passed,
        "c002_idempotency_passed": c002_passed,
        "c003_fail_closed_passed": c003_passed,
        "live_production_claimed": live_production_claimed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _c001_pass(payload: G006Payload) -> bool:
    return (
        payload["scenario_id"] == "C001"
        and payload["gateway_api_runtime_created"] is True
        and payload["session_persisted"] is True
        and payload["resume_succeeded"] is True
        and payload["session_id"] == "session-g006-001"
        and payload["run_id"] == "run-g006-001"
        and payload["goal_contract_id"] == "goal-g006-001"
        and payload["audit_record_created"] is True
        and payload["audit_records"] >= 2
        and payload["gateway_session_count"] == 1
        and payload["loopback_http_opened"] is False
        and payload["external_delivery_opened"] is False
        and payload["webhook_registered"] is False
        and payload["standing_order_created"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _c002_pass(payload: G006Payload) -> bool:
    return (
        payload["scenario_id"] == "C002"
        and payload["idempotency_replay_stable"] is True
        and payload["replay_audit_records"] == 2
        and payload["conflict_reason"] == "idempotency_conflict"
        and payload["conflict_status_code"] == 409
        and payload["gateway_session_count"] == 1
        and payload["side_effect_count"] == 0
        and payload["handler_executed"] is False
        and payload["external_delivery_opened"] is False
        and payload["webhook_registered"] is False
        and payload["standing_order_created"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _c003_pass(payload: G006Payload) -> bool:
    return (
        payload["scenario_id"] == "C003"
        and payload["unauthenticated"] == "unauthenticated"
        and payload["non_loopback_host"] == "non_loopback_blocked"
        and payload["webhook"] == "webhook_blocked"
        and payload["external_delivery"] == "external_delivery_blocked"
        and payload["standing_order"] == "standing_order_blocked"
        and payload["handler_executed"] is False
        and payload["external_delivery_opened"] is False
        and payload["webhook_registered"] is False
        and payload["standing_order_created"] is False
        and payload["raw_secret_present"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _no_secret_echo(raw_secret: str, *payloads: G006Payload) -> bool:
    serialized = json.dumps(payloads, sort_keys=True)
    return (
        raw_secret not in serialized
        and "g006-secret-auth-token" not in serialized
        and "g006-secret-resume-token" not in serialized
        and all(payload["no_secret_echo"] is True for payload in payloads)
    )


def _live_production_claimed(*payloads: G006Payload) -> bool:
    return any(payload["live_production_claimed"] is True for payload in payloads)
