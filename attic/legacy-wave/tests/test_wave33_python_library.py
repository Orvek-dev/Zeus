from __future__ import annotations

import json
from pathlib import Path

from zeus_agent import ZeusAgent


def test_python_library_facade_exposes_chat_objective_workflow_and_catalogs(tmp_path: Path) -> None:
    # Given: a Python user creates Zeus as a library object.
    agent = ZeusAgent(home=tmp_path)

    # When: the user exercises the main Hermes-style library surfaces.
    chat = agent.chat("hello Zeus")
    objective = agent.compile_objective("Build a governed workflow")
    workflow = agent.workflow_compile(
        "Implement provider, MCP catalog, cron, and review slices",
        task_count=5,
        requires_code=True,
    )
    catalogs = agent.catalogs()

    # Then: the API is usable without live side effects or objective authority widening.
    assert chat["assistant_message"].startswith("Zeus is here")
    assert objective["status"] == "compiled"
    assert workflow["selected_pattern"] == "fan_out_and_synthesize"
    assert catalogs["provider_count"] == 16
    assert catalogs["toolset_count"] == 25
    assert catalogs["mcp_catalog_entry_count"] == 25
    assert agent.live_production_claimed is False
    assert chat["live_production_claimed"] is False
    assert workflow["live_production_claimed"] is False


def test_python_library_research_brief_redacts_secret_like_query(tmp_path: Path) -> None:
    # Given: a user accidentally includes a token-like string in a library call.
    raw_secret = "sk-wave33-secret"
    agent = ZeusAgent(home=tmp_path)

    # When: the research brief surface handles the query.
    brief = agent.research_brief("compare MCP tools token={0}".format(raw_secret))
    serialized = json.dumps(brief, sort_keys=True)

    # Then: the library does not echo raw secret material.
    assert brief["decision"] == "planned"
    assert raw_secret not in serialized
    assert brief["no_secret_echo"] is True
