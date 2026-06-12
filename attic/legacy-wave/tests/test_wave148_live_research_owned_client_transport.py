from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_owned_client_transport_runtime import (
    LiveResearchOwnedClientReceipt,
    LiveResearchOwnedClientRequest,
    LiveResearchOwnedClientTransportRuntime,
)
from tests.test_wave141_live_research_external_transport import _research_policy


class _FakeResearchClient:
    def __init__(self, receipt: LiveResearchOwnedClientReceipt) -> None:
        self.receipt = receipt
        self.requests: list[LiveResearchOwnedClientRequest] = []

    def search(self, request: LiveResearchOwnedClientRequest) -> LiveResearchOwnedClientReceipt:
        self.requests.append(request)
        return self.receipt


def test_research_owned_client_executes_and_emits_external_transport_result() -> None:
    policy = _research_policy()
    client = _FakeResearchClient(_receipt())

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=client,
        execution_ref="research-owned-client://wave148/github",
    )

    assert result.decision == "executed"
    assert result.research_owned_client is True
    assert result.request_constructed is True
    assert result.policy_bound is True
    assert result.source_pin_bound is True
    assert result.research_invoked is True
    assert result.network_opened is True
    assert result.non_loopback_network_opened is True
    assert result.controlled_external_side_effects is True
    assert result.credential_material_accessed is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False
    assert result.external_transport_result is not None
    assert result.external_transport_result.decision == "executed"
    assert client.requests[0].query == policy.query
    assert client.requests[0].source_pin_ref == policy.source_pin_ref
    assert "ghp_" + "wave148" not in json.dumps(result.to_payload())
    assert result.no_secret_echo is True


def test_research_owned_client_blocks_unapproved_policy_before_client_call() -> None:
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id="github",
        query="parallel coding workflow",
        live_search_requested=True,
        source_pin_ref="source-pin://research/github",
    )
    client = _FakeResearchClient(_receipt())

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=client,
        execution_ref="research-owned-client://wave148/policy-block",
    )

    assert result.decision == "blocked"
    assert "live_research_policy_not_activation_planned" in result.blocked_reasons
    assert client.requests == []
    assert result.network_opened is False
    assert result.research_invoked is False


def test_research_owned_client_blocks_receipt_mismatch_after_request() -> None:
    receipt = _receipt().model_copy(
        update={
            "source_pin_ref": "source-pin://research/wrong",
            "cleanup_receipt": "missing-cleanup",
        },
    )

    result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=_research_policy(),
        client=_FakeResearchClient(receipt),
        execution_ref="research-owned-client://wave148/mismatch",
    )

    assert result.decision == "blocked"
    assert "research_source_pin_mismatch" in result.blocked_reasons
    assert "research_owned_client_cleanup_receipt_invalid" in result.blocked_reasons
    assert result.request_constructed is True
    assert result.network_opened is False


def test_cli_and_python_library_research_owned_client_transport() -> None:
    policy = _research_policy()
    receipt = _receipt()

    completed = CliRunner().invoke(
        app,
        [
            "live-research-owned-client-transport",
            "--policy-json",
            policy.model_dump_json(),
            "--client-receipt-json",
            receipt.model_dump_json(),
            "--execution-ref",
            "research-owned-client://wave148/github",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_owned_client_transport(
        policy.to_payload(),
        receipt.model_dump(mode="json"),
        execution_ref="research-owned-client://wave148/github-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "executed"
    assert payload["research_owned_client"] is True
    assert payload["external_transport_result"]["decision"] == "executed"
    assert payload["network_opened"] is True
    assert payload["live_production_claimed"] is False
    assert library_payload["decision"] == "executed"


def _receipt() -> LiveResearchOwnedClientReceipt:
    return LiveResearchOwnedClientReceipt(
        status_code=200,
        latency_ms=44,
        source_pin_ref="source-pin://research/github",
        result_count=2,
        response_payload={
            "items": [{"title": "Orvek-dev/Zeus", "url": "https://github.com/Orvek-dev/Zeus"}],
            "debug": "token=ghp_" + "wave148",
        },
        network_opened=True,
        non_loopback_network_opened=True,
        cleanup_receipt="research-owned-client-closed",
    )
