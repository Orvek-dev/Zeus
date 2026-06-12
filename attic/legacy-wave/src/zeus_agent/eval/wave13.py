from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union

from zeus_agent.wave13_production_scenarios import (
    wave13_blocks_payload,
    wave13_production_payload,
)

Wave13EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave13EvalPayload = dict[str, Wave13EvalValue]


@dataclass(frozen=True)
class AdjacentEvalSmoke:
    available: bool
    passed: bool


def run_wave13_eval() -> Wave13EvalPayload:
    with TemporaryDirectory(prefix="zeus-wave13-eval-") as raw_home:
        home = Path(raw_home) / "wave13-state"
        happy = wave13_production_payload(home=home)
        blocked = wave13_blocks_payload(home=home, raw_secret="sk-wave13-eval-secret")
    local_checks = [
        _check("production_scaffolds", _production_pass(happy)),
        _check("fail_closed_blocks", _blocks_pass(blocked)),
        _check("side_effects_closed", _side_effects_pass(happy, blocked)),
        _check("redaction", blocked["raw_secret_present"] is False),
    ]
    adjacent = {
        "wave9": _run_optional_eval("zeus_agent.eval.wave9", "run_wave9_eval"),
        "wave10": _run_optional_eval("zeus_agent.eval.wave10", "run_wave10_eval"),
        "wave11": _run_optional_eval("zeus_agent.eval.wave11", "run_wave11_eval"),
        "final": _run_optional_eval(
            "zeus_agent.eval.final_architecture",
            "run_final_architecture_eval",
        ),
        "wave12": _run_optional_eval("zeus_agent.eval.wave12", "run_wave12_eval"),
    }
    checks = [
        *local_checks,
        *[
            _check("{0}_eval_smoke".format(name), smoke.passed)
            for name, smoke in adjacent.items()
            if smoke.available
        ],
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave13",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "wave13_eval_total": len(local_checks),
        "wave13_eval_failed": len(local_checks)
        - sum(1 for check in local_checks if check["status"] == "pass"),
        "wave9_eval_passed": adjacent["wave9"].passed,
        "wave9_lease_eval_passed": adjacent["wave9"].passed,
        "wave10_eval_passed": adjacent["wave10"].passed,
        "wave10_provider_eval_passed": adjacent["wave10"].passed,
        "wave11_eval_passed": adjacent["wave11"].passed,
        "wave11_tool_eval_passed": adjacent["wave11"].passed,
        "final_eval_passed": adjacent["final"].passed,
        "final_architecture_eval_passed": adjacent["final"].passed,
        "wave12_eval_available": adjacent["wave12"].available,
        "wave12_eval_passed": adjacent["wave12"].passed,
        "adjacent_surface_still_works": _adjacent_surface_passed(adjacent),
        "governance_gates_ok": total == passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _production_pass(payload: dict[str, object]) -> bool:
    return (
        payload["gateway_draft_created"] is True
        and payload["api_draft_execution_recorded"] is True
        and payload["cron_job_planned"] is True
        and payload["scheduled_objective_job_created"] is True
        and payload["memory_session_fts_recorded"] is True
        and payload["skill_candidate_queued"] is True
        and payload["skill_promoted"] is False
        and payload["regression_surface_created"] is True
        and payload["live_transport_allowed"] is False
    )


def _blocks_pass(payload: dict[str, object]) -> bool:
    return (
        payload["gateway_without_lease"] == "blocked"
        and payload["cron_without_lease"] == "blocked"
        and payload["duplicate_schedule_idempotent"] is True
        and payload["conflicting_schedule_replay"] == "blocked"
        and payload["memory_raw_secret_redacted"] is True
        and payload["skill_auto_promotion"] == "blocked"
        and payload["live_transport_enablement"] == "blocked"
    )


def _side_effects_pass(
    happy: dict[str, object],
    blocked: dict[str, object],
) -> bool:
    return (
        happy["handler_executed"] is False
        and happy["network_opened"] is False
        and blocked["unleased_live_transport_opened"] is False
    )


def _run_optional_eval(module_name: str, function_name: str) -> AdjacentEvalSmoke:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return AdjacentEvalSmoke(available=False, passed=False)
        raise
    runner = getattr(module, function_name, None)
    if runner is None:
        return AdjacentEvalSmoke(available=False, passed=False)
    payload = runner()
    if not isinstance(payload, dict):
        return AdjacentEvalSmoke(available=True, passed=False)
    return AdjacentEvalSmoke(
        available=True,
        passed=payload.get("failed") == 0,
    )


def _adjacent_surface_passed(adjacent: dict[str, AdjacentEvalSmoke]) -> bool:
    required = ("wave9", "wave10", "wave11", "wave12", "final")
    return all(adjacent[name].available and adjacent[name].passed for name in required)
