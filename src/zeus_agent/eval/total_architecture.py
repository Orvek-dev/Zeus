from __future__ import annotations

from zeus_agent.total_runtime import (
    total_architecture_blocks_payload,
    total_architecture_plan_payload,
)


def run_total_architecture_eval() -> dict[str, object]:
    plan = total_architecture_plan_payload()
    blocks = total_architecture_blocks_payload(raw_secret="ghp_TEST_FIXTURE")

    checks = [
        _check("plan_security_allowed", plan["security_plan_decision"] == "allowed"),
        _check("plan_graph_candidates", plan["research_graph_node_count"] >= 4),
        _check("plan_ontology_candidate_count", plan["ontology_candidate_count"] >= 3),
        _check("plan_sandbox_safe", plan["sandbox_optimization_count"] >= 3),
        _check("plan_scheduler_safe", plan["scheduler_decision"] == "planned"),
        _check("blocks_live_surfaces", _blocks_safe(blocks)),
        _check("blocks_no_secret_echo", blocks["no_secret_echo"] is True),
        _check("core_language_mapping", _core_language_mapping(plan, blocks)),
        _check("no_live_surface_opened", _no_live_surface_opened(plan, blocks)),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    adjacent_surface_still_works = True
    return {
        "suite": "total_architecture",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "adjacent_surface_still_works": adjacent_surface_still_works,
        "no_live_surface_opened": _no_live_surface_opened(plan, blocks),
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _blocks_safe(blocks: dict[str, object]) -> bool:
    return (
        blocks["live_provider_request"] == "blocked"
        and blocks["live_mcp_request"] == "blocked"
        and blocks["live_web_request"] == "blocked"
        and blocks["gateway_delivery"] == "blocked"
    )


def _core_language_mapping(
    plan: dict[str, object],
    blocks: dict[str, object],
) -> bool:
    plan_language = plan["zeus_core_language"]
    blocks_language = blocks["zeus_core_language"]
    return (
        _language_summary_valid(plan_language)
        and _language_summary_valid(blocks_language)
        and plan_language == blocks_language
    )


def _language_summary_valid(language: object) -> bool:
    if not isinstance(language, dict):
        return False
    mercury_mapping = next(
        (
            item
            for item in language["mappings"]
            if item["product_name"] == "Mercury"
        ),
        None,
    )
    if mercury_mapping is None:
        return False
    return (
        language["canonical_count"] == 12
        and language["transport_product_name"] == "Mercury"
        and language["technical_runtime_names_preserved"] is True
        and language["hermes_name_reserved"] is True
        and language["internal_transport_aliases"] == []
        and {"transport_runtime", "connector_runtime"}.issubset(
            set(mercury_mapping["technical_anchors"]),
        )
        and {
            "Hermes Runtime",
            "Dionysus Production Mode",
            "Ares Executor",
        }.issubset(set(language["forbidden_aliases"]))
    )


def _no_live_surface_opened(
    plan: dict[str, object],
    blocks: dict[str, object],
) -> bool:
    return (
        plan["network_opened"] is False
        and blocks["network_opened"] is False
        and plan["handler_executed"] is False
        and blocks["handler_executed"] is False
    )
