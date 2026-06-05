from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime
from tests.test_wave144_live_research_ontology_registry import _ingestion


def test_live_research_ontology_registry_deletes_record_by_id(tmp_path: Path) -> None:
    runtime = LiveResearchOntologyRegistryRuntime(tmp_path)
    recorded = runtime.record(
        ingestion=_ingestion(),
        record_ref="ontology-candidate-record://wave145/delete",
    )

    deleted = runtime.delete(
        record_id=recorded.record_id or "",
        deletion_ref="ontology-candidate-delete://wave145/delete",
    )

    assert deleted.decision == "deleted"
    assert deleted.deleted_count == 1
    assert deleted.record_count == 0
    assert deleted.network_opened is False
    assert deleted.credential_material_accessed is False
    assert runtime.list().record_count == 0


def test_live_research_ontology_registry_delete_blocks_unknown_record(tmp_path: Path) -> None:
    runtime = LiveResearchOntologyRegistryRuntime(tmp_path)
    runtime.record(
        ingestion=_ingestion(),
        record_ref="ontology-candidate-record://wave145/keep",
    )

    deleted = runtime.delete(
        record_id="missing-record",
        deletion_ref="ontology-candidate-delete://wave145/missing",
    )

    assert deleted.decision == "blocked"
    assert "record_not_found" in deleted.blocked_reasons
    assert runtime.list().record_count == 1


def test_cli_and_python_library_live_research_ontology_registry_delete(tmp_path: Path) -> None:
    ingestion = _ingestion()
    runtime = LiveResearchOntologyRegistryRuntime(tmp_path)
    recorded = runtime.record(
        ingestion=ingestion,
        record_ref="ontology-candidate-record://wave145/cli",
    )

    completed = CliRunner().invoke(
        app,
        [
            "live-research-ontology-record-delete",
            "--home",
            str(tmp_path),
            "--record-id",
            recorded.record_id or "",
            "--deletion-ref",
            "ontology-candidate-delete://wave145/cli",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "deleted"
    assert payload["deleted_count"] == 1

    second = ZeusAgent(home=tmp_path).live_research_ontology_record(
        ingestion.to_payload(),
        record_ref="ontology-candidate-record://wave145/library",
    )
    library_payload = ZeusAgent(home=tmp_path).live_research_ontology_record_delete(
        record_id=second["record_id"],
        deletion_ref="ontology-candidate-delete://wave145/library",
    )
    assert library_payload["decision"] == "deleted"
    assert ZeusAgent(home=tmp_path).live_research_ontology_records()["record_count"] == 0
