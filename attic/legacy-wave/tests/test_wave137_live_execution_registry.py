from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_registry_runtime import LiveExecutionRegistryRuntime
from zeus_agent.live_execution_status_runtime import LiveExecutionStatusRuntime
from tests.test_wave136_live_execution_status import _review
from tests.test_wave135_live_execution_bundle_review import _bundle


def test_live_execution_registry_records_and_lists_status(tmp_path: Path) -> None:
    status = _status()
    runtime = LiveExecutionRegistryRuntime(tmp_path)

    recorded = runtime.record(status=status, record_ref="live-execution-record://wave137/reviewed")
    listed = runtime.list()

    assert recorded.decision == "recorded"
    assert recorded.record_id is not None
    assert recorded.record_count == 1
    assert recorded.network_opened is False
    assert recorded.credential_material_accessed is False
    assert recorded.live_production_claimed is False
    assert listed.decision == "listed"
    assert listed.record_count == 1
    assert listed.records[0]["decision"] == "reviewed"


def test_live_execution_registry_blocks_secret_echo_status(tmp_path: Path) -> None:
    unsafe = _status().model_copy(update={"no_secret_echo": False})
    runtime = LiveExecutionRegistryRuntime(tmp_path)

    result = runtime.record(status=unsafe, record_ref="live-execution-record://wave137/unsafe")

    assert result.decision == "blocked"
    assert "status_secret_echo_detected" in result.blocked_reasons
    assert runtime.list().record_count == 0


def test_cli_and_python_library_live_execution_registry(tmp_path: Path) -> None:
    status = _status()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-execution-record",
            "--home",
            str(tmp_path),
            "--status-json",
            status.model_dump_json(),
            "--record-ref",
            "live-execution-record://wave137/cli",
            "--json",
        ],
    )
    listed = runner.invoke(
        app,
        ["live-execution-records", "--home", str(tmp_path), "--json"],
    )

    assert completed.exit_code == 0, completed.stdout
    assert listed.exit_code == 0, listed.stdout
    assert json.loads(completed.stdout)["decision"] == "recorded"
    assert json.loads(listed.stdout)["record_count"] == 1

    library_payload = ZeusAgent(home=tmp_path).live_execution_record(
        status.to_payload(),
        record_ref="live-execution-record://wave137/library",
    )
    library_list = ZeusAgent(home=tmp_path).live_execution_records()
    assert library_payload["decision"] == "recorded"
    assert library_list["record_count"] == 2


def _status():
    bundle = _bundle()
    review = _review(bundle)
    return LiveExecutionStatusRuntime().build(bundle=bundle, review=review)
