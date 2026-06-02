from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union

from zeus_agent.eval.wave10 import run_wave10_eval
from zeus_agent.eval.wave11 import run_wave11_eval
from zeus_agent.wave12_conversation_scenarios import (
    wave12_cli_eval_smoke_success,
    wave12_conversation_blocks_payload,
    wave12_conversation_happy_payload,
)

Wave12EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave12EvalPayload = dict[str, Wave12EvalValue]


def run_wave12_eval() -> Wave12EvalPayload:
    with TemporaryDirectory(prefix="zeus-wave12-eval-") as raw_home:
        happy = wave12_conversation_happy_payload(
            message="Inspect repo, call echo tool, summarize evidence",
            home=Path(raw_home),
        )
    blocked = wave12_conversation_blocks_payload(
        raw_secret="ghp_TEST_FIXTURE",
    )
    wave10 = run_wave10_eval()
    wave11 = run_wave11_eval()
    checks = [
        _check("conversation_runtime", _happy_pass(happy)),
        _check("blocked_cases", _blocked_pass(blocked)),
        _check("wave10_provider_eval", wave10["failed"] == 0),
        _check("wave11_tool_eval", wave11["failed"] == 0),
        _check("verification_engine_gate", happy["verification_completion_allowed"] is True),
        _check("cli_eval_smoke", wave12_cli_eval_smoke_success()),
        _check("adjacent_surface", wave10["failed"] == 0 and wave11["failed"] == 0),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave12",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "wave10_provider_eval_passed": wave10["failed"] == 0,
        "wave11_tool_eval_passed": wave11["failed"] == 0,
        "verification_engine_gate_passed": happy["verification_completion_allowed"] is True,
        "cli_eval_smoke_success": any(
            check["name"] == "cli_eval_smoke" and check["status"] == "pass"
            for check in checks
        ),
        "adjacent_surface_still_works": wave10["failed"] == 0 and wave11["failed"] == 0,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: dict[str, object]) -> bool:
    return (
        payload["conversation_runtime_created"] is True
        and payload["provider_invoked"] is True
        and payload["tool_schema_compiled"] is True
        and payload["tool_call_planned"] is True
        and payload["broker_dispatch_allowed"] is True
        and payload["tool_result_recorded"] is True
        and payload["session_lineage_recorded"] is True
        and payload["context_compressed"] is False
        and payload["verification_completion_allowed"] is True
        and payload["handler_executed"] is True
        and payload["network_opened"] is False
        and payload["no_secret_echo"] is True
    )


def _blocked_pass(payload: dict[str, object]) -> bool:
    return (
        payload["empty_message"] == "blocked"
        and payload["malformed_tool_call"] == "blocked"
        and payload["missing_runtime_lease"] == "blocked"
        and payload["provider_fallback_recorded"] is True
        and payload["retry_limit_enforced"] is True
        and payload["unsafe_context_injection"] == "blocked"
        and payload["unknown_tool"] == "blocked"
        and payload["completion_gate_blocks_missing_evidence"] is True
        and payload["handler_executed"] is False
        and payload["network_opened"] is False
        and payload["raw_secret_present"] is False
    )
