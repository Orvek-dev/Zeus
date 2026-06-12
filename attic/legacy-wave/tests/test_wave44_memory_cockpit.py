from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.memory_cockpit_runtime import MemoryCockpitRuntime
from zeus_agent.memory_graph_runtime import MemoryGraphStore


def test_memory_cockpit_reports_empty_local_store(tmp_path: Path) -> None:
    # Given: the user asks for the memory cockpit on a fresh local store.
    result = MemoryCockpitRuntime(tmp_path).build()

    # Then: Zeus reports local-first memory status without live claims.
    assert result.decision == "report"
    assert result.fact_count == 0
    assert result.quarantined_count == 0
    assert result.selected_subject is None
    assert "zeus memory-fact-add" in result.recommended_next_commands
    assert result.memory_store_local is True
    assert result.live_production_claimed is False


def test_memory_cockpit_renders_subject_wiki_page(tmp_path: Path) -> None:
    # Given: a subject has a proposed MemoryGraph fact.
    MemoryGraphStore(tmp_path).propose_fact(
        subject="Hermes",
        predicate="absorbed_surface",
        object_text="MCP catalog and provider runtime.",
        provenance_id="evidence-wave44-001",
    )

    # When: the cockpit is opened for the subject.
    result = MemoryCockpitRuntime(tmp_path).build(subject="Hermes")

    # Then: the LLM Wiki view is surfaced as a reviewable page.
    assert result.selected_subject == "Hermes"
    assert result.wiki_page is not None
    assert result.wiki_page["fact_count"] == 1
    assert "MCP catalog and provider runtime." in result.wiki_page["body"]
    assert result.live_production_claimed is False


def test_memory_cockpit_counts_quarantine_without_secret_echo(tmp_path: Path) -> None:
    # Given: a secret-like memory fact is proposed and quarantined.
    raw_secret = "sk-" + "wave44-secret"
    MemoryGraphStore(tmp_path).propose_fact(
        subject="Credential",
        predicate="accidental_log",
        object_text="token={0}".format(raw_secret),
        provenance_id="evidence-wave44-002",
    )

    # Then: the cockpit reports quarantine and never echoes the raw secret.
    result = MemoryCockpitRuntime(tmp_path).build(subject="Credential")
    serialized = result.model_dump_json()
    assert result.quarantined_count == 1
    assert result.no_secret_echo is True
    assert raw_secret not in serialized


def test_cli_exposes_memory_cockpit(tmp_path: Path) -> None:
    # Given: memory exists for a subject in the local store.
    MemoryGraphStore(tmp_path).propose_fact(
        subject="Zeus",
        predicate="core_value",
        object_text="Purpose-oriented governed execution.",
        provenance_id="evidence-wave44-003",
    )

    # When: the user opens the remember cockpit from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "remember", "--home", str(tmp_path), "--subject", "Zeus", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI returns the local wiki page and memory counts.
    assert payload["decision"] == "report"
    assert payload["selected_subject"] == "Zeus"
    assert payload["wiki_page"]["fact_count"] == 1
    assert payload["memory_store_local"] is True


def test_python_library_exposes_memory_cockpit(tmp_path: Path) -> None:
    # Given: a Python user has a ZeusAgent home with memory.
    MemoryGraphStore(tmp_path).propose_fact(
        subject="Zeus",
        predicate="core_value",
        object_text="Purpose-oriented governed execution.",
        provenance_id="evidence-wave44-004",
    )

    # Then: the library returns the same JSON-compatible memory cockpit.
    payload = ZeusAgent(home=tmp_path).remember_status(subject="Zeus")
    assert payload["decision"] == "report"
    assert payload["wiki_page"]["fact_count"] == 1
    assert payload["live_production_claimed"] is False
