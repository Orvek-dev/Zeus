from __future__ import annotations

from typing import Union

from zeus_agent.wave19_research_provider_scenarios import (
    Wave19Payload,
    wave19_research_provider_blocks_payload,
    wave19_research_provider_payload,
)

Wave19EvalValue = Union[bool, int, str, list[dict[str, str]]]
Wave19EvalPayload = dict[str, Wave19EvalValue]


def run_wave19_eval() -> Wave19EvalPayload:
    happy = wave19_research_provider_payload()
    blocked = wave19_research_provider_blocks_payload(raw_secret="sk-wave19-eval-secret")
    checks = [
        _check("research_provider_happy", _happy_pass(happy)),
        _check("research_provider_blocks", _blocks_pass(blocked)),
        _check("no_secret_echo", blocked["raw_secret_present"] is False),
        _check("no_live_production_claim", _live_production_claimed(happy, blocked) is False),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave19",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "research_provider_happy_passed": _happy_pass(happy),
        "research_provider_blocks_passed": _blocks_pass(blocked),
        "live_production_claimed": _live_production_claimed(happy, blocked),
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _happy_pass(payload: Wave19Payload) -> bool:
    return (
        payload["web_provider_created"] is True
        and payload["github_provider_created"] is True
        and payload["fake_web_provider_called"] is True
        and payload["fake_github_provider_called"] is True
        and payload["web_source_planned"] is True
        and payload["github_source_planned"] is True
        and payload["source_pins_created"] >= 2
        and payload["fresh_sources_accepted"] is True
        and payload["graph_created"] is True
        and payload["graph_node_count"] >= 3
        and payload["citation_edge_count"] >= 3
        and payload["external_claims_pinned"] is True
        and payload["stale_source_blocked"] is False
        and payload["handler_executed"] is False
        and payload["network_opened"] is False
        and payload["client_constructed"] is False
        and payload["subprocess_started"] is False
        and payload["real_web_adapter_used"] is False
        and payload["real_github_adapter_used"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _blocks_pass(payload: Wave19Payload) -> bool:
    return (
        payload["unpinned_web_source"] == "blocked"
        and payload["missing_web_source_ref"] == "blocked"
        and payload["stale_web_source"] == "blocked"
        and payload["secret_web_summary"] == "blocked"
        and payload["github_missing_ref"] == "blocked"
        and payload["github_missing_query_evidence"] == "blocked"
        and payload["unpinned_github_source"] == "blocked"
        and payload["stale_github_source"] == "blocked"
        and payload["secret_github_query"] == "blocked"
        and payload["stale_graph_source"] == "blocked"
        and payload["unpinned_graph_external_claim"] == "blocked"
        and payload["duplicate_graph_node"] == "blocked"
        and payload["missing_edge_target"] == "blocked"
        and payload["blocked_handler_executed"] is False
        and payload["blocked_network_opened"] is False
        and payload["client_constructed"] is False
        and payload["subprocess_started"] is False
        and payload["real_web_adapter_used"] is False
        and payload["real_github_adapter_used"] is False
        and payload["raw_secret_present"] is False
        and payload["no_secret_echo"] is True
        and payload["live_production_claimed"] is False
    )


def _live_production_claimed(happy: Wave19Payload, blocked: Wave19Payload) -> bool:
    return happy["live_production_claimed"] is True or blocked["live_production_claimed"] is True
