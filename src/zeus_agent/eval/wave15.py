from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union

from zeus_agent.wave15_live_agent_scenarios import (
    wave15_live_agent_blocks_payload,
    wave15_live_agent_payload,
)

Wave15ScenarioValue = Union[bool, int, str, tuple[str, ...]]
Wave15ScenarioPayload = Mapping[str, Wave15ScenarioValue]
Wave15EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave15EvalPayload = dict[str, Wave15EvalValue]


@dataclass(frozen=True)
class AdjacentEvalSmoke:
    available: bool
    passed: bool


def run_wave15_eval() -> Wave15EvalPayload:
    with TemporaryDirectory(prefix="zeus-wave15-eval-") as raw_home:
        home = Path(raw_home) / "wave15-state"
        happy = wave15_live_agent_payload(home=home)
        blocked = wave15_live_agent_blocks_payload(
            home=home,
            raw_secret="sk-wave15-eval-secret",
        )
    wave12 = _run_eval("zeus_agent.eval.wave12", "run_wave12_eval")
    wave14 = _run_eval("zeus_agent.eval.wave14", "run_wave14_eval")
    checks = [
        _check("live_agent_loop_created", happy["live_agent_loop_created"] is True),
        _check("provider_tool_loop_completed", _happy_pass(happy)),
        _check("audit_record_created", _audit_pass(happy, blocked)),
        _check("live_agent_blocks_closed", _blocks_pass(blocked)),
        _check("no_secret_echo", blocked["raw_secret_present"] is False),
        _check("wave12_adjacent", wave12.available and wave12.passed),
        _check("wave14_adjacent", wave14.available and wave14.passed),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    live_production_claimed = _live_production_claimed(happy, blocked)
    no_live_network_opened = happy["network_opened"] is False and blocked["network_opened"] is False
    return {
        "suite": "wave15",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "wave12_adjacent_passed": wave12.available and wave12.passed,
        "wave14_adjacent_passed": wave14.available and wave14.passed,
        "live_production_claimed": live_production_claimed,
        "no_live_network_opened": no_live_network_opened,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: Wave15ScenarioPayload) -> bool:
    return (
        payload["provider_decision"] == "selected"
        and isinstance(payload["provider_turns"], int)
        and payload["provider_turns"] >= 2
        and payload["streaming_chunks_recorded"] is True
        and isinstance(payload["tool_calls_processed"], int)
        and payload["tool_calls_processed"] >= 1
        and payload["tool_result_recorded"] is True
        and isinstance(payload["evidence_records"], int)
        and payload["evidence_records"] >= 2
        and isinstance(payload["audit_events"], int)
        and payload["audit_events"] >= 1
        and payload["audit_record_created"] is True
        and payload["session_persisted"] is True
        and payload["verification_completion_allowed"] is True
        and payload["handler_executed"] is True
        and payload["network_opened"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _blocks_pass(payload: Wave15ScenarioPayload) -> bool:
    return (
        payload["empty_message"] == "blocked"
        and payload["malformed_tool_call"] == "blocked"
        and payload["missing_provider_lease"] == "blocked"
        and payload["missing_tool_lease"] == "blocked"
        and payload["unknown_tool"] == "blocked"
        and payload["message_too_large"] == "blocked"
        and payload["large_message_provider_attempts"] == 0
        and payload["retry_limit_enforced"] is True
        and isinstance(payload["retry_provider_attempts"], int)
        and payload["retry_provider_attempts"] >= 2
        and payload["cancellation_recorded"] is True
        and payload["cancellation_provider_attempts"] == 0
        and payload["fallback_route_recorded"] is True
        and payload["fallback_completed"] is True
        and payload["fallback_handler_executed"] is True
        and isinstance(payload["fallback_provider_attempts"], int)
        and payload["fallback_provider_attempts"] >= 3
        and payload["unsafe_context_injection"] == "blocked"
        and payload["handler_executed"] is False
        and payload["network_opened"] is False
        and isinstance(payload["audit_events"], int)
        and payload["audit_events"] >= 1
        and payload["audit_record_created"] is True
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _audit_pass(happy: Wave15ScenarioPayload, blocked: Wave15ScenarioPayload) -> bool:
    return (
        isinstance(happy["audit_events"], int)
        and happy["audit_events"] >= 1
        and happy["audit_record_created"] is True
        and isinstance(blocked["audit_events"], int)
        and blocked["audit_events"] >= 1
        and blocked["audit_record_created"] is True
    )


def _live_production_claimed(
    happy: Wave15ScenarioPayload,
    blocked: Wave15ScenarioPayload,
) -> bool:
    return (
        happy["live_production_claimed"] is True
        or blocked["live_production_claimed"] is True
    )


def _run_eval(module_name: str, function_name: str) -> AdjacentEvalSmoke:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return AdjacentEvalSmoke(available=False, passed=False)
        raise
    runner = getattr(module, function_name, None)
    if runner is None:
        return AdjacentEvalSmoke(available=True, passed=False)
    payload = runner()
    if not isinstance(payload, dict):
        return AdjacentEvalSmoke(available=True, passed=False)
    return AdjacentEvalSmoke(available=True, passed=payload.get("failed") == 0)
