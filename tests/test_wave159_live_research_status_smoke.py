from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeResult
from zeus_agent.live_research_status_runtime import LiveResearchStatusRuntime


def test_live_research_status_absorbs_loopback_smoke_without_external_evidence() -> None:
    policy = _policy("web")
    smoke = _smoke("web")

    result = LiveResearchStatusRuntime().build(policy=policy, loopback_smoke_result=smoke)

    assert result.decision == "smoke_ready"
    assert result.loopback_smoke_result_bound is True
    assert result.loopback_smoke_execution_id == smoke.execution_id
    assert result.loopback_network_seen is True
    assert result.external_result_bound is False
    assert result.external_network_seen is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_research_status_blocks_smoke_source_mismatch() -> None:
    result = LiveResearchStatusRuntime().build(policy=_policy("web"), loopback_smoke_result=_smoke("community"))

    assert result.decision == "blocked"
    assert "research_loopback_smoke_policy_mismatch" in result.blocked_reasons
    assert result.external_result_bound is False


def test_cli_and_python_library_live_research_status_with_smoke_result() -> None:
    policy = _policy("community")
    smoke = _smoke("community")
    completed = CliRunner().invoke(
        app,
        [
            "live-research-status",
            "--policy-json",
            policy.model_dump_json(),
            "--loopback-smoke-result-json",
            smoke.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_status(
        policy=policy.to_payload(),
        loopback_smoke_result=smoke.to_payload(),
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "smoke_ready"
    assert payload["loopback_smoke_result_bound"] is True
    assert payload["external_result_bound"] is False
    assert library_payload["decision"] == "smoke_ready"


def _policy(source_id: str):
    return LiveResearchActivationPolicyRuntime().plan(
        source_id=source_id,
        query="parallel coding workflow",
        live_search_requested=True,
        approval_ref=f"approval://research/{source_id}",
        source_pin_ref=f"source-pin://research/{source_id}",
        max_results=5,
        rate_limit_per_minute=30,
    )


def _smoke(source_id: str) -> LiveResearchLoopbackSmokeResult:
    return LiveResearchLoopbackSmokeResult(
        decision="smoke_executed",
        execution_id=f"live-research-smoke-{source_id}",
        execution_ref=f"live-research-smoke://wave159/{source_id}",
        adapter_id=source_id,
        source_id=source_id,
        endpoint="http://127.0.0.1:9123/search",
        status_code=200,
        latency_ms=1,
        result_count=1,
        redacted_response={"items": [{"title": "smoke", "url": "https://docs.example.dev"}]},
        cleanup_receipt="research-owned-client-closed",
        client_constructed=True,
        research_invoked=True,
        network_opened=True,
        non_loopback_network_opened=False,
        external_evidence_ready=False,
        live_production_claimed=False,
    )
