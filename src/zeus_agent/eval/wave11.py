from __future__ import annotations

from typing import Union

from zeus_agent.wave11_tool_scenarios import (
    wave11_tool_mcp_blocks_payload,
    wave11_tool_mcp_happy_payload,
)

Wave11EvalValue = Union[int, str, list[dict[str, str]]]
Wave11EvalPayload = dict[str, Wave11EvalValue]
Wave11Payload = dict[str, object]


def run_wave11_eval() -> Wave11EvalPayload:
    happy = wave11_tool_mcp_happy_payload()
    blocked = wave11_tool_mcp_blocks_payload(
        raw_secret="ghp_TEST_FIXTURE",
    )
    checks = [
        _check("tool_registry_compiled", happy["tool_registry_compiled"] is True),
        _check("schema_visibility", _schema_visibility_pass(happy)),
        _check("dispatch_allowed", _dispatch_allowed_pass(happy)),
        _check("happy_side_effects_closed", _happy_side_effects_pass(happy)),
        _check("block_labels", _block_labels_pass(blocked)),
        _check("blocked_side_effects_closed", _blocked_side_effects_pass(blocked)),
        _check("redaction", _redaction_pass(happy, blocked)),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave11",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _schema_visibility_pass(payload: Wave11Payload) -> bool:
    return (
        payload["toolset_enabled"] is True
        and payload["toolset_disabled_hidden"] is True
        and payload["mcp_discovery_normalized"] is True
        and payload["model_visible_schema_count>=2"] is True
        and payload["local_tool_schema_visible"] is True
        and payload["mcp_tool_schema_visible"] is True
    )


def _dispatch_allowed_pass(payload: Wave11Payload) -> bool:
    return (
        payload["broker_dispatch_allowed"] is True
        and payload["mcp_dispatch_allowed"] is True
        and payload["runtime_lease_validated"] is True
        and payload["transport_registry_allowed"] is True
    )


def _happy_side_effects_pass(payload: Wave11Payload) -> bool:
    return (
        payload["handler_executed"] is True
        and payload["network_opened"] is False
        and payload["credential_material_accessed"] is False
    )


def _block_labels_pass(payload: Wave11Payload) -> bool:
    return (
        payload["missing_runtime_lease"] == "blocked"
        and payload["expired_runtime_lease"] == "blocked"
        and payload["disabled_toolset"] == "blocked"
        and payload["unknown_tool"] == "blocked"
        and payload["malformed_mcp_discovery"] == "blocked"
        and payload["malformed_tool_arguments"] == "blocked"
        and payload["capability_widening"] == "blocked"
        and payload["transport_mismatch"] == "blocked"
        and payload["unhealthy_transport"] == "blocked"
        and payload["over_budget"] == "blocked"
    )


def _blocked_side_effects_pass(payload: Wave11Payload) -> bool:
    return (
        payload["handler_executed"] is False
        and payload["client_constructed"] is False
        and payload["network_opened"] is False
        and payload["credential_material_accessed"] is False
    )


def _redaction_pass(happy: Wave11Payload, blocked: Wave11Payload) -> bool:
    return (
        happy["result_redacted"] is True
        and happy["no_secret_echo"] is True
        and blocked["schema_injection_redacted"] is True
        and blocked["raw_secret_result_redacted"] is True
        and blocked["no_secret_echo"] is True
        and blocked["raw_secret_present"] is False
    )
