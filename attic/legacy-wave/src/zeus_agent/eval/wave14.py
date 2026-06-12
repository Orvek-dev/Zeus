from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union

from zeus_agent.wave14_live_connection_scenarios import (
    wave14_live_blocks_payload,
    wave14_live_plan_payload,
)
from zeus_agent.wave14_orchestra_scenarios import wave14_orchestra_plan_payload

Wave14ScenarioValue = Union[bool, int, str, tuple[str, ...]]
Wave14ScenarioPayload = Mapping[str, Wave14ScenarioValue]
Wave14EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave14EvalPayload = dict[str, Wave14EvalValue]


@dataclass(frozen=True)
class AdjacentEvalSmoke:
    available: bool
    passed: bool


def run_wave14_eval() -> Wave14EvalPayload:
    with TemporaryDirectory(prefix="zeus-wave14-eval-") as raw_home:
        home = Path(raw_home) / "wave14-state"
        happy = wave14_live_plan_payload(home=home)
        blocked = wave14_live_blocks_payload(
            home=home,
            raw_secret="sk-wave14-eval-secret",
        )
        orchestra = wave14_orchestra_plan_payload(home=home)
        orchestra_blocked = wave14_orchestra_plan_payload(
            home=home,
            scenario="blocked-route",
        )
    local_checks = [
        _check("live_connection_planned", _happy_pass(happy)),
        _check(
            "live_connection_runtime_api_available",
            happy["live_connection_runtime_api_available"] is True,
        ),
        _check("live_connection_route_count", _planned_surfaces_pass(happy)),
        _check("all_live_blocks", _blocks_pass(blocked)),
        _check("live_connection_block_reasons", _block_reasons_pass(blocked)),
        _check("side_effects_closed", _side_effects_pass(happy, blocked)),
        _check("no_secret_echo", blocked["raw_secret_present"] is False),
        _check("no_live_production_claim", _no_live_production_claim(happy, blocked)),
        _check("orchestra_plan_planned", _orchestra_planned(orchestra)),
        _check(
            "orchestra_recovery_cleanup",
            _orchestra_recovery_cleanup(orchestra, orchestra_blocked),
        ),
    ]
    adjacent = {
        "wave9": _run_eval("zeus_agent.eval.wave9", "run_wave9_eval"),
        "wave10": _run_eval("zeus_agent.eval.wave10", "run_wave10_eval"),
        "wave11": _run_eval("zeus_agent.eval.wave11", "run_wave11_eval"),
        "wave12": _run_eval("zeus_agent.eval.wave12", "run_wave12_eval"),
        "wave13": _run_eval("zeus_agent.eval.wave13", "run_wave13_eval"),
        "final": _run_eval(
            "zeus_agent.eval.final_architecture",
            "run_final_architecture_eval",
        ),
    }
    checks = [
        *local_checks,
        *[
            _check("{0}_eval_smoke".format(name), smoke.available and smoke.passed)
            for name, smoke in adjacent.items()
        ],
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    local_passed = sum(1 for check in local_checks if check["status"] == "pass")
    adjacent_ok = _adjacent_surface_passed(adjacent)
    live_production_claimed = _live_production_claimed(happy, blocked)
    return {
        "suite": "wave14",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "wave14_eval_total": len(local_checks),
        "wave14_eval_failed": len(local_checks) - local_passed,
        "adjacent_surface_still_works": adjacent_ok,
        "wave9_eval_passed": adjacent["wave9"].passed,
        "wave10_eval_passed": adjacent["wave10"].passed,
        "wave11_eval_passed": adjacent["wave11"].passed,
        "wave12_eval_passed": adjacent["wave12"].passed,
        "wave13_eval_passed": adjacent["wave13"].passed,
        "final_architecture_eval_passed": adjacent["final"].passed,
        "live_production_claimed": live_production_claimed,
        "governance_gates_ok": total == passed and live_production_claimed is False,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: Wave14ScenarioPayload) -> bool:
    return (
        payload["objective_contract_bound"] is True
        and payload["live_connection_router_created"] is True
        and payload["decision"] == "planned"
        and payload["dry_run"] is True
        and payload["live_transport_allowed"] is False
        and payload["planned_provider_route"] is True
        and payload["planned_mcp_route"] is True
        and payload["planned_web_route"] is True
        and payload["planned_gateway_route"] is True
        and payload["planned_sandbox_route"] is True
        and payload["audit_record_created"] is True
    )


def _planned_surfaces_pass(payload: Wave14ScenarioPayload) -> bool:
    return (
        isinstance(payload["route_count"], int)
        and payload["route_count"] >= 5
        and set(payload["planned_surface_kinds"]) >= {
            "provider",
            "mcp",
            "web",
            "gateway",
            "sandbox",
        }
    )


def _blocks_pass(payload: Wave14ScenarioPayload) -> bool:
    return (
        payload["missing_lease_blocked"] is True
        and payload["missing_approval_blocked"] is True
        and payload["credential_mismatch_blocked"] is True
        and payload["mcp_prompt_injection_blocked"] is True
        and payload["unpinned_web_research_blocked"] is True
        and payload["sandbox_egress_blocked"] is True
        and payload["plugin_quarantine_blocked"] is True
        and payload["gateway_target_blocked"] is True
    )


def _block_reasons_pass(payload: Wave14ScenarioPayload) -> bool:
    return set(payload["blocked_reasons"]) >= {
        "missing_lease",
        "missing_approval",
        "credential_scope_mismatch",
        "mcp_prompt_injection",
        "web_source_unpinned",
        "sandbox_network_command_blocked",
        "plugin_quarantined",
        "gateway_target_blocked",
    }


def _side_effects_pass(
    happy: Wave14ScenarioPayload,
    blocked: Wave14ScenarioPayload,
) -> bool:
    return (
        happy["handler_executed"] is False
        and happy["network_opened"] is False
        and blocked["handler_executed"] is False
        and blocked["network_opened"] is False
    )


def _no_live_production_claim(
    happy: Wave14ScenarioPayload,
    blocked: Wave14ScenarioPayload,
) -> bool:
    return (
        happy["live_production_claimed"] is False
        and blocked["live_production_claimed"] is False
    )


def _orchestra_planned(payload: Wave14ScenarioPayload) -> bool:
    return (
        payload["orchestra_decision"] == "planned"
        and payload["parallel_schedule_decision"] == "planned"
        and payload["live_plan_decision"] == "planned"
        and payload["wave_count"] == 2
        and set(payload["planned_surface_kinds"]) >= {
            "provider",
            "mcp",
            "github",
            "browser",
            "terminal",
        }
        and payload["handler_executed"] is False
        and payload["network_opened"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _orchestra_recovery_cleanup(
    happy: Wave14ScenarioPayload,
    blocked: Wave14ScenarioPayload,
) -> bool:
    return (
        happy["cleanup_obligation_required"] is True
        and happy["replay_available"] is False
        and blocked["orchestra_decision"] == "blocked"
        and blocked["replay_available"] is True
        and blocked["handler_executed"] is False
        and blocked["network_opened"] is False
        and blocked["raw_secret_present"] is False
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
    return AdjacentEvalSmoke(
        available=True,
        passed=payload.get("failed") == 0,
    )


def _adjacent_surface_passed(adjacent: dict[str, AdjacentEvalSmoke]) -> bool:
    required = ("wave9", "wave10", "wave11", "wave12", "wave13", "final")
    return all(adjacent[name].available and adjacent[name].passed for name in required)


def _live_production_claimed(
    happy: Wave14ScenarioPayload,
    blocked: Wave14ScenarioPayload,
) -> bool:
    return (
        happy["live_production_claimed"] is True
        or blocked["live_production_claimed"] is True
    )
