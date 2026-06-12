from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_external_transport_runtime import (
    LiveResearchExternalClientResult,
    LiveResearchExternalTransportRuntime,
)


def test_research_external_transport_absorbs_source_pinned_result_with_redaction() -> None:
    result = LiveResearchExternalTransportRuntime().execute(
        policy=_research_policy(),
        client_result=_client_result(),
        execution_ref="research-external://wave141/github",
    )

    assert result.decision == "executed"
    assert result.policy_bound is True
    assert result.source_pin_bound is True
    assert result.research_invoked is True
    assert result.live_search_enabled is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.cleanup_receipt == "research-external-client-closed"
    assert "ghp_" + "wave141" not in json.dumps(result.to_payload())
    assert result.no_secret_echo is True
    assert result.live_production_claimed is False


def test_research_external_transport_blocks_policy_without_approval() -> None:
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        source_pin_ref="source-pin://research/github",
    )

    result = LiveResearchExternalTransportRuntime().execute(
        policy=policy,
        client_result=_client_result(),
        execution_ref="research-external://wave141/policy-block",
    )

    assert result.decision == "blocked"
    assert "live_research_policy_not_activation_planned" in result.blocked_reasons
    assert result.network_opened is False
    assert result.research_invoked is False


def test_research_external_transport_blocks_source_pin_and_cleanup_mismatch() -> None:
    client_result = _client_result().model_copy(
        update={
            "source_pin_ref": "source-pin://research/wrong",
            "cleanup_receipt": "missing-cleanup",
        },
    )

    result = LiveResearchExternalTransportRuntime().execute(
        policy=_research_policy(),
        client_result=client_result,
        execution_ref="research-external://wave141/mismatch",
    )

    assert result.decision == "blocked"
    assert "research_source_pin_mismatch" in result.blocked_reasons
    assert "research_external_cleanup_receipt_invalid" in result.blocked_reasons
    assert result.network_opened is False
    assert result.live_search_enabled is False


def test_cli_and_python_library_research_external_transport() -> None:
    policy = _research_policy()
    client_result = _client_result()
    completed = CliRunner().invoke(
        app,
        [
            "live-research-external-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--client-result-json",
            client_result.model_dump_json(),
            "--execution-ref",
            "research-external://wave141/github",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_external_transport(
        policy.to_payload(),
        client_result.model_dump(mode="json"),
        execution_ref="research-external://wave141/github-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["controlled_external_side_effects"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _research_policy():
    return LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        approval_ref="approval://research/github",
        source_pin_ref="source-pin://research/github",
        max_results=5,
        rate_limit_per_minute=30,
    )


def _client_result() -> LiveResearchExternalClientResult:
    return LiveResearchExternalClientResult(
        status_code=200,
        latency_ms=52,
        source_pin_ref="source-pin://research/github",
        result_count=2,
        response_payload={
            "items": [{"title": "Orvek-dev/Zeus", "url": "https://github.com/Orvek-dev/Zeus"}],
            "debug": "token=ghp_" + "wave141",
        },
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="research-external-client-closed",
    )
