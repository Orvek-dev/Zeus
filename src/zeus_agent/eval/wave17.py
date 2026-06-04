from __future__ import annotations

from typing import Union

from zeus_agent.wave17_mcp_manager_scenarios import (
    Wave17Payload,
    wave17_mcp_manager_blocks_payload,
    wave17_mcp_manager_payload,
)

Wave17EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave17EvalPayload = dict[str, Wave17EvalValue]


def run_wave17_eval() -> Wave17EvalPayload:
    happy = wave17_mcp_manager_payload()
    blocked = wave17_mcp_manager_blocks_payload(raw_secret="sk-wave17-eval-secret")
    checks = [
        _check("mcp_manager_happy", _happy_pass(happy)),
        _check("mcp_manager_blocks", _blocks_pass(blocked)),
        _check("no_secret_echo", blocked["raw_secret_present"] is False),
        _check("no_live_production_claim", _live_production_claimed(happy, blocked) is False),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave17",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "mcp_manager_happy_passed": _happy_pass(happy),
        "mcp_manager_blocks_passed": _blocks_pass(blocked),
        "live_production_claimed": _live_production_claimed(happy, blocked),
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: Wave17Payload) -> bool:
    return (
        payload["manager_created"] is True
        and payload["lifecycle_started"] == 2
        and payload["lifecycle_stopped"] == 2
        and payload["compiled_tool_count"] == 2
        and payload["dynamic_list_changed_refresh"] is True
        and payload["refreshed_tool_count"] >= 3
        and payload["schema_redacted"] is True
        and payload["parallel_metadata_stable"] is True
        and payload["shutdown_cleanup"] is True
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _blocks_pass(payload: Wave17Payload) -> bool:
    return (
        payload["malformed_stdio_discovery"] == "blocked"
        and payload["malformed_http_discovery"] == "blocked"
        and payload["unpinned_server"] == "blocked"
        and payload["non_loopback_http_endpoint"] == "blocked"
        and payload["prompt_injection_description"] == "quarantined"
        and payload["secret_like_description"] == "quarantined"
        and payload["secret_like_schema_redacted"] is True
        and payload["resources_prompts_wrappers_enabled"] is False
        and payload["include_exclude_empty"] == "blocked"
        and payload["duplicate_tool_name"] == "blocked"
        and payload["blocked_request_count"] == 0
        and payload["handler_executed"] is False
        and payload["subprocess_started_for_blocked"] is False
        and payload["network_opened_for_blocked"] is False
        and payload["raw_secret_present"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _live_production_claimed(happy: Wave17Payload, blocked: Wave17Payload) -> bool:
    return happy["live_production_claimed"] is True or blocked["live_production_claimed"] is True
