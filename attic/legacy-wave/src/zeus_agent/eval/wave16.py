from __future__ import annotations

from typing import Union

from zeus_agent.wave16_provider_live_scenarios import (
    Wave16Payload,
    wave16_provider_live_blocks_payload,
    wave16_provider_live_payload,
)

Wave16EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave16EvalPayload = dict[str, Wave16EvalValue]


def run_wave16_eval() -> Wave16EvalPayload:
    happy = wave16_provider_live_payload()
    blocked = wave16_provider_live_blocks_payload(raw_secret="sk-wave16-eval-secret")
    checks = [
        _check("provider_http_happy", _happy_pass(happy)),
        _check("provider_http_blocks", _blocks_pass(blocked)),
        _check("no_secret_echo", blocked["raw_secret_present"] is False),
        _check("no_live_production_claim", _live_production_claimed(happy, blocked) is False),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave16",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "provider_http_happy_passed": _happy_pass(happy),
        "provider_http_blocks_passed": _blocks_pass(blocked),
        "live_production_claimed": _live_production_claimed(happy, blocked),
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: Wave16Payload) -> bool:
    return (
        payload["openai_compatible_provider"] == "selected"
        and payload["local_llm_provider"] == "selected"
        and payload["openai_http_request_count"] == 1
        and payload["local_http_request_count"] == 1
        and payload["approval_receipt_checked"] is True
        and payload["timeout_enforced"] is True
        and payload["runtime_lease_validated"] is True
        and payload["credential_scope_bound"] is True
        and payload["audit_record_created"] is True
        and payload["non_loopback_network_opened"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _blocks_pass(payload: Wave16Payload) -> bool:
    return (
        payload["missing_runtime_lease"] == "blocked"
        and payload["missing_approval"] == "blocked"
        and payload["missing_timeout"] == "blocked"
        and payload["live_network_required"] == "blocked"
        and payload["non_loopback_endpoint"] == "blocked"
        and payload["network_host_mismatch"] == "blocked"
        and payload["missing_credential_scope"] == "blocked"
        and payload["unsafe_credential"] == "blocked"
        and payload["invalid_approval"] == "blocked"
        and payload["approval_missing_capability"] == "blocked"
        and payload["malformed_http_response"] == "blocked"
        and payload["malformed_tool_call_missing_id"] == "blocked"
        and payload["malformed_tool_call_bad_arguments"] == "blocked"
        and payload["http_status_error"] == "blocked"
        and payload["blocked_http_request_count"] == 0
        and payload["malformed_http_request_count"] == 1
        and payload["malformed_tool_call_request_count"] == 2
        and payload["http_status_request_count"] == 1
        and payload["http_status_network_opened"] is True
        and payload["authorized_error_handler_executed"] is False
        and payload["authorized_error_network_opened"] is True
        and payload["raw_secret_present"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _live_production_claimed(happy: Wave16Payload, blocked: Wave16Payload) -> bool:
    return happy["live_production_claimed"] is True or blocked["live_production_claimed"] is True
