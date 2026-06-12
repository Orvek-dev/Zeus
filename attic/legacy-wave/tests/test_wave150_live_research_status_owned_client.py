from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_owned_client_transport_runtime import (
    LiveResearchOwnedClientTransportRuntime,
    StaticResearchOwnedClient,
)
from zeus_agent.live_research_status_runtime import LiveResearchStatusRuntime
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave148_live_research_owned_client_transport import _receipt


def test_live_research_status_absorbs_owned_client_result_as_external_ready() -> None:
    policy = _research_policy()
    owned_result = _owned_result()

    result = LiveResearchStatusRuntime().build(
        policy=policy,
        owned_client_result=owned_result,
        external_result=None,
        graph_result=None,
        ingestion=None,
        registry_record=None,
    )

    assert result.decision == "external_ready"
    assert result.owned_client_result_bound is True
    assert result.external_result_bound is True
    assert result.owned_client_execution_id == owned_result.execution_id
    assert result.external_network_seen is True
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_research_status_blocks_unexecuted_owned_client_result() -> None:
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        source_pin_ref="source-pin://research/github",
    )
    owned_result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=StaticResearchOwnedClient(_receipt()),
        execution_ref="research-owned-client://wave150/policy-block",
    )

    result = LiveResearchStatusRuntime().build(
        policy=policy,
        owned_client_result=owned_result,
        external_result=None,
        graph_result=None,
        ingestion=None,
        registry_record=None,
    )

    assert result.decision == "blocked"
    assert "research_owned_client_not_executed" in result.blocked_reasons
    assert result.external_result_bound is False
    assert result.network_opened is False


def test_cli_and_python_library_live_research_status_owned_client() -> None:
    policy = _research_policy()
    owned_result = _owned_result()
    completed = CliRunner().invoke(
        app,
        [
            "live-research-status",
            "--policy-json",
            policy.model_dump_json(),
            "--owned-client-result-json",
            owned_result.model_dump_json(),
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_status(
        policy=policy.to_payload(),
        owned_client_result=owned_result.to_payload(),
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "external_ready"
    assert payload["owned_client_result_bound"] is True
    assert payload["external_result_bound"] is True
    assert payload["network_opened"] is False
    assert library_payload["decision"] == "external_ready"


def _owned_result():
    return LiveResearchOwnedClientTransportRuntime().execute(
        policy=_research_policy(),
        client=StaticResearchOwnedClient(_receipt()),
        execution_ref="research-owned-client://wave150/github",
    )
