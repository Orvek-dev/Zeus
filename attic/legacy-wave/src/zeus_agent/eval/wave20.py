from __future__ import annotations

from typing import Optional, Union

from zeus_agent.wave20_observability_scenarios import (
    Wave20Payload,
    wave20_observability_blocks_payload,
    wave20_observability_payload,
)

Wave20EvalValue = Optional[Union[bool, int, str, list[dict[str, str]]]]
Wave20EvalPayload = dict[str, Wave20EvalValue]


def run_wave20_eval() -> Wave20EvalPayload:
    happy = wave20_observability_payload()
    blocked = wave20_observability_blocks_payload(raw_secret="sk-wave20-eval-secret")
    checks = [
        _check("observability_happy", _happy_pass(happy)),
        _check("observability_blocks", _blocks_pass(blocked)),
        _check("no_secret_echo", happy["no_secret_echo"] is True and blocked["no_secret_echo"] is True),
        _check("no_live_production_claim", _live_production_claimed(happy, blocked) is False),
        _check("release_claim_blocked", blocked["release_claim"] == "blocked"),
        _check("independent_review_evidence_bound", _review_evidence_bound(happy)),
        _check("production_release_blocked", happy["production_release_blocked"] is True),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave20",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "observability_gates_ok": total == passed,
        "observability_happy_passed": _happy_pass(happy),
        "observability_blocks_passed": _blocks_pass(blocked),
        "no_secret_echo": happy["no_secret_echo"] is True and blocked["no_secret_echo"] is True,
        "release_claim_blocked": blocked["release_claim"] == "blocked",
        "production_release_blocked": happy["production_release_blocked"] is True,
        "release_approval_evidence_id": happy["release_approval_evidence_id"],
        "live_production_claimed": _live_production_claimed(happy, blocked),
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: Wave20Payload) -> bool:
    return (
        payload["observability_gate_created"] is True
        and payload["trace_span_count"] >= 4
        and payload["audit_log_count"] >= 4
        and payload["evidence_matrix_rows"] >= 6
        and payload["threat_model_gate"] == "pass"
        and payload["secret_echo_gate"] == "pass"
        and payload["release_no_claim_gate"] == "pass"
        and payload["production_release_blocked"] is True
        and payload["release_approval_evidence_id"] is None
        and payload["independent_review_recorded"] is True
        and _review_evidence_bound(payload)
        and payload["manual_qa_channel_recorded"] is True
        and payload["handler_executed"] is False
        and payload["network_opened"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _blocks_pass(payload: Wave20Payload) -> bool:
    return (
        payload["missing_threat_model"] == "blocked"
        and payload["missing_evidence"] == "blocked"
        and payload["stale_evidence"] == "blocked"
        and payload["secret_echo"] == "blocked"
        and payload["release_claim"] == "blocked"
        and payload["missing_independent_review"] == "blocked"
        and payload["malformed_gate_record"] == "blocked"
        and payload["blocked_handler_executed"] is False
        and payload["blocked_network_opened"] is False
        and payload["raw_secret_present"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _live_production_claimed(happy: Wave20Payload, blocked: Wave20Payload) -> bool:
    return happy["live_production_claimed"] is True or blocked["live_production_claimed"] is True


def _review_evidence_bound(payload: Wave20Payload) -> bool:
    evidence_id = payload["independent_review_evidence_id"]
    return isinstance(evidence_id, str) and evidence_id.startswith("review.g007.")
