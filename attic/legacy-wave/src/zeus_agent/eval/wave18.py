from __future__ import annotations

from typing import Union

from zeus_agent.wave18_tool_sandbox_scenarios import (
    Wave18Payload,
    wave18_tool_sandbox_blocks_payload,
    wave18_tool_sandbox_payload,
)

Wave18EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave18EvalPayload = dict[str, Wave18EvalValue]


def run_wave18_eval() -> Wave18EvalPayload:
    happy = wave18_tool_sandbox_payload()
    blocked = wave18_tool_sandbox_blocks_payload(raw_secret="sk-wave18-eval-secret")
    checks = [
        _check("tool_sandbox_happy", _happy_pass(happy)),
        _check("tool_sandbox_blocks", _blocks_pass(blocked)),
        _check("no_secret_echo", blocked["raw_secret_present"] is False),
        _check("no_live_production_claim", _live_production_claimed(happy, blocked) is False),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave18",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "tool_sandbox_happy_passed": _happy_pass(happy),
        "tool_sandbox_blocks_passed": _blocks_pass(blocked),
        "live_production_claimed": _live_production_claimed(happy, blocked),
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: Wave18Payload) -> bool:
    return (
        payload["sandbox_executor_created"] is True
        and payload["runtime_lease_validated"] is True
        and payload["broker_dispatch_used"] is True
        and payload["safe_file_read_allowed"] is True
        and payload["safe_file_write_allowed_with_approval"] is True
        and payload["safe_cli_command_allowed"] is True
        and payload["command_stdout_recorded"] is True
        and payload["evidence_record_created"] is True
        and payload["path_scope_enforced"] is True
        and payload["safe_env_used"] is True
        and payload["handler_executed"] is True
        and payload["network_opened"] is False
        and payload["docker_socket_mounted"] is False
        and payload["unbounded_execution"] is False
        and payload["credential_material_accessed"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _blocks_pass(payload: Wave18Payload) -> bool:
    return (
        payload["missing_runtime_lease"] == "blocked"
        and payload["expired_runtime_lease"] == "blocked"
        and payload["hostile_root"] == "blocked"
        and payload["authority_widening"] == "blocked"
        and payload["missing_approval"] == "blocked"
        and payload["invalid_approval"] == "blocked"
        and payload["approval_replay"] == "blocked"
        and payload["network_command"] == "blocked"
        and payload["destructive_command"] == "blocked"
        and payload["out_of_scope_path"] == "blocked"
        and payload["credential_path"] == "blocked"
        and payload["cloud_credential_path"] == "blocked"
        and payload["credential_command"] == "blocked"
        and payload["recursive_credential_command"] == "blocked"
        and payload["dash_pattern_recursive_grep"] == "blocked"
        and payload["malformed_file_request"] == "blocked"
        and payload["malformed_action"] == "blocked"
        and payload["malformed_root"] == "blocked"
        and payload["docker_socket_mount"] == "blocked"
        and payload["docker_backend"] == "blocked"
        and payload["open_egress"] == "blocked"
        and payload["unbounded_resource"] == "blocked"
        and payload["timeout_or_unbounded_execution"] == "blocked"
        and payload["blocked_handler_executed"] is False
        and payload["allowed_error_network_opened"] is False
        and payload["raw_secret_present"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _live_production_claimed(happy: Wave18Payload, blocked: Wave18Payload) -> bool:
    return happy["live_production_claimed"] is True or blocked["live_production_claimed"] is True
