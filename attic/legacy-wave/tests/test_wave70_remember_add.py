from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.memory_entry_runtime import MemoryEntryRuntime


def test_remember_add_records_local_proposed_fact(tmp_path: Path) -> None:
    result = MemoryEntryRuntime(tmp_path).add(
        subject="Zeus",
        predicate="core_value",
        object_text="Purpose-oriented governed execution.",
        provenance_id="wave70.evidence.local",
    )

    assert result.decision == "recorded"
    assert result.selected_fact["subject"] == "Zeus"
    assert result.selected_fact["status"] == "proposed"
    assert result.fact_count == 1
    assert result.quarantined_count == 0
    assert result.memory_promoted is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_remember_add_quarantines_secret_like_content_without_echo(tmp_path: Path) -> None:
    raw_secret = "sk-" + "wave70-secret"

    result = MemoryEntryRuntime(tmp_path).add(
        subject="Credential",
        predicate="accidental_log",
        object_text="token={0}".format(raw_secret),
        provenance_id="wave70.evidence.secret",
    )
    blob = result.model_dump_json()

    assert result.decision == "recorded"
    assert result.selected_fact["status"] == "quarantined"
    assert result.quarantined_count == 1
    assert raw_secret not in blob
    assert result.no_secret_echo is True


def test_cli_remember_add_and_subject_view_share_store(tmp_path: Path) -> None:
    runner = CliRunner()

    added = runner.invoke(
        app,
        [
            "remember",
            "--add",
            "--subject",
            "Hermes",
            "--predicate",
            "absorbed_surface",
            "--object-text",
            "MCP catalog and provider runtime.",
            "--provenance-id",
            "wave70.evidence.cli",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    viewed = runner.invoke(
        app,
        ["remember", "--subject", "Hermes", "--home", str(tmp_path), "--json"],
    )

    assert added.exit_code == 0, added.stdout
    assert viewed.exit_code == 0, viewed.stdout
    added_payload = json.loads(added.stdout)
    viewed_payload = json.loads(viewed.stdout)
    assert added_payload["decision"] == "recorded"
    assert added_payload["selected_fact"]["status"] == "proposed"
    assert viewed_payload["wiki_page"]["fact_count"] == 1
    assert "MCP catalog and provider runtime." in viewed_payload["wiki_page"]["body"]
    assert viewed_payload["live_production_claimed"] is False


def test_cli_remember_add_blocks_missing_fields(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["remember", "--add", "--subject", "Zeus", "--home", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["decision"] == "blocked"
    assert "missing_memory_fields" in payload["blocked_reasons"]
    assert payload["memory_promoted"] is False


def test_python_library_exposes_remember_add(tmp_path: Path) -> None:
    agent = ZeusAgent(home=tmp_path)

    added = agent.remember_add(
        subject="Zeus",
        predicate="core_value",
        object_text="Purpose-oriented governed execution.",
        provenance_id="wave70.evidence.library",
    )
    viewed = agent.remember_status(subject="Zeus")

    assert added["decision"] == "recorded"
    assert added["selected_fact"]["status"] == "proposed"
    assert viewed["wiki_page"]["fact_count"] == 1
    assert viewed["live_production_claimed"] is False
