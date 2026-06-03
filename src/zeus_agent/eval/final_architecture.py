from __future__ import annotations

from collections.abc import Mapping

from zeus_agent.product_runtime import (
    final_adversarial_blocks_payload,
    final_core_contracts_payload,
    final_state_persistence_payload,
)


def run_final_architecture_eval() -> dict[str, object]:
    from tempfile import TemporaryDirectory
    from pathlib import Path

    core = final_core_contracts_payload(
        objective=(
            "Implement final Zeus architecture with Objective Compiler, Work Loop, "
            "Verification Engine, Promotion controls, and Skill Evolution."
        ),
        raw_secret="ghp_TEST_FIXTURE",
    )
    adversarial = final_adversarial_blocks_payload(raw_secret="sk-final-eval-secret")
    with TemporaryDirectory(prefix="zeus-final-eval-") as raw_home:
        state = final_state_persistence_payload(
            home=Path(raw_home),
            raw_secret="ghp_TEST_FIXTURE",
        )
    checks = [
        _check("objective_compiled", core["objective_compiled"] is True),
        _check("work_loop_plan_created", core["work_loop_plan_created"] is True),
        _check("verification_obligations", int(core["verification_obligations"]) >= 5),
        _check("promotion_live_disabled", core["promotion_live_transport"] is False),
        _check(
            "skill_candidate_proposed_only",
            core["skill_evolution_candidate_status"] == "proposed_not_promoted",
        ),
        _check("adversarial_blocks", _adversarial_blocks_pass(adversarial)),
        _check("core_language_mapping", _core_language_mapping_pass(core)),
        _check("no_secret_echo", core["no_secret_echo"] is True and adversarial["no_secret_echo"] is True),
        _check("product_state_reload_stable", state["product_state_reload_stable"] is True),
        _check("adjacent_surface_still_works", core["adjacent_surface_still_works"] is True),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "final_architecture",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "final_product_tests_passed": passed == total,
        "adjacent_surface_still_works": core["adjacent_surface_still_works"],
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _adversarial_blocks_pass(payload: dict[str, object]) -> bool:
    return (
        payload["boundary_empty_malformed_proof"] is True
        and payload["empty_objective"] == "blocked"
        and payload["malformed_constraint"] == "blocked"
        and payload["prompt_injection"] == "flagged"
        and payload["authority_widening"] == "blocked"
        and payload["live_transport_not_authorized"] == "blocked"
        and payload["unsafe_skill_auto_promotion"] == "blocked"
        and payload["handler_executed"] is False
        and payload["network_opened"] is False
    )


def _core_language_mapping_pass(payload: dict[str, object]) -> bool:
    core_language = payload.get("core_domain_language")
    if not isinstance(core_language, Mapping):
        return False
    return (
        core_language.get("canonical_count") == 12
        and core_language.get("transport_product_name") == "Mercury"
        and core_language.get("technical_runtime_names_preserved") is True
        and core_language.get("hermes_name_reserved") is True
    )
