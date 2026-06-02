from __future__ import annotations

import json

from zeus_agent.wave9_scenarios import (
    wave9_runtime_blocks_payload,
    wave9_runtime_lease_payload,
)


def run_wave9_eval() -> dict[str, object]:
    happy = wave9_runtime_lease_payload()
    blocked = wave9_runtime_blocks_payload(
        raw_secret="ghp_TEST_FIXTURE",
    )
    checks = [
        _check("runtime_lease_validated", happy["runtime_lease_validated"] is True),
        _check("all_runtime_scopes_allowed", _happy_scopes_pass(happy)),
        _check("credential_scope_label_only", _credential_label_pass(happy)),
        _check("fail_closed_blocks", _blocks_pass(blocked)),
        _check("expired_lease_fail_closed", _expired_lease_pass(blocked)),
        _check("budget_and_evidence_scope", _budget_evidence_pass(happy)),
        _check("handler_network_closed", _side_effects_pass(happy, blocked)),
        _check("no_secret_echo", _no_secret_echo_pass(happy, blocked)),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave9",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_scopes_pass(payload: dict[str, object]) -> bool:
    return (
        payload["provider_scope"] == "allowed"
        and payload["mcp_scope"] == "allowed"
        and payload["gateway_scope"] == "allowed"
        and payload["cron_scope"] == "allowed"
        and payload["api_tool_scope"] == "allowed"
        and payload["plugin_scope"] == "allowed"
    )


def _credential_label_pass(payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, sort_keys=True)
    return (
        payload["credential_scope_label"] == "external.openai.readonly"
        and "ghp_" not in serialized
        and "sk-" not in serialized
    )


def _blocks_pass(payload: dict[str, object]) -> bool:
    return (
        payload["missing_runtime_lease"] == "blocked"
        and payload["malformed_principal"] == "blocked"
        and payload["malformed_runtime_lease"] == "blocked"
        and payload["runtime_kind_capability_mismatch"] == "blocked"
        and payload["authority_widening"] == "blocked"
        and payload["scope_escalation"] == "blocked"
        and payload["evidence_scope_bypass"] == "blocked"
        and payload["unsafe_credential"] == "blocked"
        and payload["live_network_without_scope"] == "blocked"
        and payload["expired_runtime_lease"] == "blocked"
        and payload["over_budget"] == "blocked"
    )


def _expired_lease_pass(payload: dict[str, object]) -> bool:
    return payload["expired_runtime_lease"] == "blocked"


def _budget_evidence_pass(payload: dict[str, object]) -> bool:
    return payload["budget_limit"] == 10_000 and payload["evidence_target"] == "mneme.wave9.runtime_lease"


def _side_effects_pass(
    happy: dict[str, object],
    blocked: dict[str, object],
) -> bool:
    return (
        happy["handler_executed"] is False
        and happy["network_opened"] is False
        and blocked["handler_executed"] is False
        and blocked["network_opened"] is False
    )


def _no_secret_echo_pass(
    happy: dict[str, object],
    blocked: dict[str, object],
) -> bool:
    return happy["no_secret_echo"] is True and blocked["no_secret_echo"] is True
