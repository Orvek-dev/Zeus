from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.wiki_runtime import render_wiki_page


def test_memory_graph_store_exports_provenanced_facts_and_wiki_page(tmp_path: Path) -> None:
    store = MemoryGraphStore(tmp_path)
    fact = store.propose_fact(
        subject="Zeus",
        predicate="core_value",
        object_text="Purpose-oriented governed execution.",
        provenance_id="evidence-wave23-001",
    )

    page = render_wiki_page(store, "Zeus")
    exported = store.export_snapshot()

    assert fact.status == "proposed"
    assert fact.provenance_id == "evidence-wave23-001"
    assert exported["fact_count"] == 1
    assert exported["quarantined_count"] == 0
    assert exported["live_production_claimed"] is False
    assert page.subject == "Zeus"
    assert page.fact_count == 1
    assert "Purpose-oriented governed execution." in page.body


def test_memory_graph_quarantines_secret_like_content_and_delete_scrubs(tmp_path: Path) -> None:
    store = MemoryGraphStore(tmp_path)
    raw_secret = "sk-wave23-secret"
    fact = store.propose_fact(
        subject="Credential",
        predicate="accidental_log",
        object_text=f"token={raw_secret}",
        provenance_id="evidence-wave23-002",
    )

    serialized_before = json.dumps(store.export_snapshot(), sort_keys=True)
    deleted = store.delete_fact(fact.fact_id)
    serialized_after = json.dumps(store.export_snapshot(include_deleted=True), sort_keys=True)

    assert fact.status == "quarantined"
    assert raw_secret not in serialized_before
    assert "secret_like_content" in fact.blocked_reasons
    assert deleted.status == "deleted"
    assert raw_secret not in serialized_after
    assert "[deleted]" in serialized_after


def test_memory_graph_quarantines_secret_like_subjects(tmp_path: Path) -> None:
    store = MemoryGraphStore(tmp_path)
    raw_secret = "sk-wave23-subject"
    fact = store.propose_fact(
        subject=f"token={raw_secret}",
        predicate="accidental_log",
        object_text="safe text",
        provenance_id="evidence-wave23-004",
    )
    serialized = json.dumps(store.export_snapshot(), sort_keys=True)

    assert fact.status == "quarantined"
    assert raw_secret not in serialized
    assert "[redacted-secret]" in serialized


def test_memory_wiki_cli_surfaces_share_local_store(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    add_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "memory-fact-add",
            "--home",
            str(tmp_path),
            "--subject",
            "Hermes",
            "--predicate",
            "absorbed_surface",
            "--object-text",
            "MCP and provider runtime patterns.",
            "--provenance-id",
            "evidence-wave23-003",
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    wiki_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "wiki-page",
            "--home",
            str(tmp_path),
            "--subject",
            "Hermes",
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert add_proc.returncode == 0, add_proc.stderr
    assert wiki_proc.returncode == 0, wiki_proc.stderr
    added = json.loads(add_proc.stdout)
    page = json.loads(wiki_proc.stdout)
    assert added["status"] == "proposed"
    assert page["fact_count"] == 1
    assert "MCP and provider runtime patterns." in page["body"]
    assert page["live_production_claimed"] is False
