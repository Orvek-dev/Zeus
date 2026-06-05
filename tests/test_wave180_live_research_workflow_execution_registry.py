from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_workflow_execution_registry_runtime import (
    LiveResearchWorkflowExecutionRegistryRuntime,
)
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusRuntime,
)
from tests.test_wave178_live_cockpit_research_workflow_loopback_executor import _executed_loopback


def test_research_workflow_execution_registry_records_lists_and_deletes_status(tmp_path: Path) -> None:
    status = _status()
    runtime = LiveResearchWorkflowExecutionRegistryRuntime(tmp_path)

    recorded = runtime.record(
        status=status,
        record_ref="research-workflow-execution-record://wave180/recorded",
    )
    listed = runtime.list()
    deleted = runtime.delete(
        record_id=recorded.record_id or "",
        deletion_ref="research-workflow-execution-delete://wave180/recorded",
    )

    assert recorded.decision == "recorded"
    assert recorded.record_id is not None
    assert recorded.record_count == 1
    assert recorded.network_opened is False
    assert recorded.credential_material_accessed is False
    assert recorded.live_production_claimed is False
    assert listed.decision == "listed"
    assert listed.record_count == 1
    assert listed.records[0]["decision"] == "execution_recorded"
    assert deleted.decision == "deleted"
    assert deleted.deleted_count == 1


def test_research_workflow_execution_registry_blocks_unsafe_status(tmp_path: Path) -> None:
    unsafe = _status().model_copy(update={"no_secret_echo": False})
    runtime = LiveResearchWorkflowExecutionRegistryRuntime(tmp_path)

    result = runtime.record(
        status=unsafe,
        record_ref="research-workflow-execution-record://wave180/unsafe",
    )

    assert result.decision == "blocked"
    assert "status_secret_echo_detected" in result.blocked_reasons
    assert runtime.list().record_count == 0


def test_research_workflow_execution_registry_cli_and_library_surface_match(tmp_path: Path) -> None:
    status = _status()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-research-workflow-execution-record",
            "--home",
            str(tmp_path),
            "--status-json",
            status.model_dump_json(),
            "--record-ref",
            "research-workflow-execution-record://wave180/cli",
            "--json",
        ],
    )
    listed = runner.invoke(
        app,
        ["live-research-workflow-execution-records", "--home", str(tmp_path), "--json"],
    )

    assert completed.exit_code == 0, completed.stdout
    assert listed.exit_code == 0, listed.stdout
    assert json.loads(completed.stdout)["decision"] == "recorded"
    assert json.loads(listed.stdout)["record_count"] == 1

    library_payload = ZeusAgent(home=tmp_path).live_research_workflow_execution_record(
        status.to_payload(),
        record_ref="research-workflow-execution-record://wave180/library",
    )
    library_list = ZeusAgent(home=tmp_path).live_research_workflow_execution_records()
    assert library_payload["decision"] == "recorded"
    assert library_list["record_count"] == 2


def _status():
    return LiveResearchWorkflowExecutionStatusRuntime().build(
        loopback_executor=_executed_loopback(),
        status_ref="research-workflow-execution-status://wave180/recorded",
        evidence_ref="evidence://wave180/recorded",
    )
