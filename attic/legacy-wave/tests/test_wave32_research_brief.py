from __future__ import annotations

import json

from zeus_agent.research_runtime import build_research_brief


def test_research_brief_builds_source_pinned_web_github_graph_without_live_io() -> None:
    # Given: a user asks Zeus to research an execution workflow.
    payload = build_research_brief(
        objective_id="wave32.research",
        query="parallel coding orchestration with tmux context bridge",
    )

    # Then: Zeus returns a source-pinned graph and no live IO claim.
    assert payload["decision"] == "planned"
    assert payload["provider_count"] == 2
    assert payload["graph_node_count"] >= 3
    assert payload["citation_edge_count"] >= 2
    assert payload["external_claims_pinned"] is True
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True
    assert "source_pinned_workflow_brief" in payload["recommendations"]


def test_research_brief_redacts_secret_like_query() -> None:
    # Given: the research query accidentally contains credential-like text.
    raw_secret = "sk-wave32-secret"

    # When: Zeus builds the research brief.
    payload = build_research_brief(
        objective_id="wave32.research",
        query="compare MCP tools token={0}".format(raw_secret),
    )
    serialized = json.dumps(payload, sort_keys=True)

    # Then: the payload keeps the brief useful but never echoes the raw secret.
    assert payload["decision"] == "planned"
    assert raw_secret not in serialized
    assert "[redacted-secret]" in serialized or "sk-...redacted" in serialized
    assert payload["no_secret_echo"] is True
