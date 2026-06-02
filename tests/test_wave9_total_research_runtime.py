from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from zeus_agent.research_runtime import (
    ResearchEvidenceEdge,
    ResearchEvidenceGraph,
    ResearchEvidenceNode,
    ResearchGraphBuilder,
    ResearchSourcePin,
)


def _make_local_doc_node(node_id: str) -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id=node_id,
        source_kind="local_doc",
        source_pin=ResearchSourcePin(
            source_type="local_doc",
            source_path="docs/notes/hermes-comparison.md",
            trust_level="high",
            provenance_id="packly.local.doc",
            summary="Local Hermes comparison draft with baseline constraints.",
        ),
    )


def _make_hermes_node(node_id: str) -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id=node_id,
        source_kind="hermes_source_pin",
        source_pin=ResearchSourcePin(
            source_type="hermes_source_pin",
            source_url="https://docs.hermes.local/compare",
            source_commit="8a2c9f4",
            trust_level="high",
            provenance_id="hermes.source.pin",
            summary="Hermes source pin for runtime comparison evidence.",
        ),
    )


def _make_openclaw_node(node_id: str) -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id=node_id,
        source_kind="openclaw_source_pin",
        source_pin=ResearchSourcePin(
            source_type="openclaw_source_pin",
            source_url="https://docs.openclaw.local/research",
            captured_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
            trust_level="medium",
            provenance_id="openclaw.source.pin",
            summary="OpenClaw source pin capturing benchmark notes.",
        ),
    )


def _make_task_node(node_id: str) -> ResearchEvidenceNode:
    return ResearchEvidenceNode(
        node_id=node_id,
        source_kind="task_evidence_node",
        source_pin=ResearchSourcePin(
            source_type="task_evidence_node",
            source_url="https://tasks.platform.local/evidence/9",
            source_commit="4e11bd9",
            trust_level="medium",
            provenance_id="task.evidence.node",
            summary="Task evidence node from internal verification log.",
        ),
    )


def test_research_graph_requires_source_pins_for_external_claims() -> None:
    with pytest.raises((ValueError, ValidationError)):
        ResearchGraphBuilder().build(
            nodes=(
                ResearchEvidenceNode(
                    node_id="hermes-raw",
                    source_kind="hermes_source_pin",
                    source_pin=None,
                ),
            )
        )


def test_embedded_secret_span_in_research_claim_is_rejected() -> None:
    secret_node = ResearchEvidenceNode(
        node_id="node-secret",
        source_kind="hermes_source_pin",
        source_pin=ResearchSourcePin(
            source_type="hermes_source_pin",
            source_url="https://docs.hermes.local/compare",
            source_commit="8a2c9f4",
            trust_level="high",
            provenance_id="hermes.source.pin",
            summary="leaked key sk-ABCDEFGHIJKLMNOP",
        ),
    )

    with pytest.raises((ValueError, ValidationError)) as exc:
        ResearchGraphBuilder().build(nodes=(secret_node,))

    assert "raw secret" not in str(exc.value).lower()

    secret_graph = ResearchEvidenceGraph(
        nodes=[secret_node],
        edges=[],
        network_opened=False,
        handler_executed=False,
    )
    assert secret_graph.no_secret_echo is False


def test_direct_research_graph_no_secret_echo_scans_source_commit() -> None:
    secret_node = ResearchEvidenceNode(
        node_id="node-source-commit-secret",
        source_kind="task_evidence_node",
        source_pin=ResearchSourcePin(
            source_type="task_evidence_node",
            source_url="https://tasks.platform.local/evidence/9",
            source_commit="sk-ABCDEFGHIJKLMNOP",
            trust_level="medium",
            provenance_id="task.evidence.node",
            summary="Source commit token hidden in metadata.",
        ),
    )

    secret_graph = ResearchEvidenceGraph(
        nodes=[secret_node],
        edges=[],
        network_opened=False,
        handler_executed=False,
    )

    assert secret_graph.no_secret_echo is False
    assert secret_node.source_pin is not None
    assert "sk-ABCDEFGHIJKLMNOP" in secret_node.source_pin.source_commit


def test_happy_graph_with_local_and_external_claim_nodes_has_expected_counts() -> None:
    graph = ResearchGraphBuilder().build(
        nodes=(
            _make_local_doc_node("node-local-doc"),
            _make_hermes_node("node-hermes-pin"),
            _make_openclaw_node("node-openclaw-pin"),
            _make_task_node("node-task"),
        ),
        edges=(
            ResearchEvidenceEdge(source_node_id="node-local-doc", target_node_id="node-hermes-pin", relation="supports"),
            ResearchEvidenceEdge(source_node_id="node-hermes-pin", target_node_id="node-openclaw-pin", relation="cross_refs"),
            ResearchEvidenceEdge(source_node_id="node-task", target_node_id="node-openclaw-pin", relation="verifies"),
            ResearchEvidenceEdge(source_node_id="node-task", target_node_id="node-hermes-pin", relation="supports"),
        ),
    )

    assert graph.node_count >= 4
    assert graph.edge_count >= 3
    assert graph.external_claims_pinned is True
    assert graph.network_opened is False
    assert graph.handler_executed is False
    assert graph.no_secret_echo is True
    assert isinstance(graph, ResearchEvidenceGraph)


def test_secret_like_summary_is_rejected_without_raw_echo() -> None:
    source_pin = ResearchSourcePin(
            source_type="hermes_source_pin",
            source_url="https://docs.hermes.local/compare",
            source_commit="8a2c9f4",
            trust_level="high",
            provenance_id="hermes.source.pin",
            summary="api_key=sk-live-REDACT_ME_NOT",
        )
    with pytest.raises((ValueError, ValidationError)) as exc:
        ResearchGraphBuilder().build(
            nodes=(
                ResearchEvidenceNode(
                    node_id="node-secret",
                    source_kind="hermes_source_pin",
                    source_pin=source_pin,
                ),
            ),
        )
    assert "raw secret" not in str(exc.value).lower()
    assert "sk-live-redact_me_not" not in str(exc.value).lower()
    assert "api_key=" not in str(exc.value).lower()


def test_builder_does_not_perform_network_handlers() -> None:
    graph = ResearchGraphBuilder().build(
        nodes=(
            _make_local_doc_node("node-local-doc"),
            _make_hermes_node("node-hermes-pin"),
            _make_openclaw_node("node-openclaw-pin"),
            _make_task_node("node-task"),
        ),
        edges=(),
    )

    assert graph.network_opened is False
    assert graph.handler_executed is False
