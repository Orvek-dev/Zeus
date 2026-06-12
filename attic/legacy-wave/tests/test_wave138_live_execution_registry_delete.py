from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_registry_runtime import LiveExecutionRegistryRuntime
from tests.test_wave137_live_execution_registry import _status


def test_live_execution_registry_deletes_record_by_id(tmp_path: Path) -> None:
    runtime = LiveExecutionRegistryRuntime(tmp_path)
    recorded = runtime.record(status=_status(), record_ref="live-execution-record://wave138/delete")

    deleted = runtime.delete(
        record_id=recorded.record_id or "",
        deletion_ref="live-execution-delete://wave138/delete",
    )

    assert deleted.decision == "deleted"
    assert deleted.deleted_count == 1
    assert deleted.record_count == 0
    assert deleted.network_opened is False
    assert deleted.credential_material_accessed is False
    assert runtime.list().record_count == 0


def test_live_execution_registry_delete_blocks_unknown_record(tmp_path: Path) -> None:
    runtime = LiveExecutionRegistryRuntime(tmp_path)
    runtime.record(status=_status(), record_ref="live-execution-record://wave138/keep")

    deleted = runtime.delete(
        record_id="missing-record",
        deletion_ref="live-execution-delete://wave138/missing",
    )

    assert deleted.decision == "blocked"
    assert "record_not_found" in deleted.blocked_reasons
    assert runtime.list().record_count == 1


def test_cli_and_python_library_live_execution_registry_delete(tmp_path: Path) -> None:
    status = _status()
    runner = CliRunner()
    recorded = LiveExecutionRegistryRuntime(tmp_path).record(
        status=status,
        record_ref="live-execution-record://wave138/cli",
    )

    completed = runner.invoke(
        app,
        [
            "live-execution-record-delete",
            "--home",
            str(tmp_path),
            "--record-id",
            recorded.record_id or "",
            "--deletion-ref",
            "live-execution-delete://wave138/cli",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "deleted"
    assert payload["deleted_count"] == 1

    second = ZeusAgent(home=tmp_path).live_execution_record(
        status.to_payload(),
        record_ref="live-execution-record://wave138/library",
    )
    library_payload = ZeusAgent(home=tmp_path).live_execution_record_delete(
        record_id=second["record_id"],
        deletion_ref="live-execution-delete://wave138/library",
    )
    assert library_payload["decision"] == "deleted"
    assert ZeusAgent(home=tmp_path).live_execution_records()["record_count"] == 0
