from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_workflow_execution_registry_runtime import (
    LiveResearchWorkflowExecutionRegistryRuntime,
)
from tests.test_wave187_live_research_workflow_execution_status_external import (
    _ready_external_execution,
)
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusRuntime,
)


def test_research_workflow_execution_registry_records_external_status_summary(tmp_path: Path) -> None:
    status = _external_status("recorded")
    runtime = LiveResearchWorkflowExecutionRegistryRuntime(tmp_path)

    recorded = runtime.record(
        status=status,
        record_ref="research-workflow-execution-record://wave188/external",
    )
    listed = runtime.list()
    cockpit = LiveCockpitRuntime().build(research_workflow_execution_registry=listed)

    assert recorded.decision == "recorded"
    assert recorded.execution_kind == "external"
    assert recorded.external_execution_record_count == 1
    assert recorded.loopback_execution_record_count == 0
    assert recorded.external_network_seen is True
    assert listed.record_count == 1
    assert listed.external_execution_record_count == 1
    assert listed.records[0]["execution_kind"] == "external"
    assert listed.records[0]["external_network_seen"] is True
    assert cockpit.research_workflow_execution_registry_external_record_count == 1
    assert cockpit.research_workflow_execution_registry_external_network_seen is True
    assert cockpit.network_opened is False


def test_research_workflow_execution_registry_external_cli_and_library_surface(tmp_path: Path) -> None:
    status = _external_status("cli")
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
            "research-workflow-execution-record://wave188/cli",
            "--json",
        ],
    )
    listed = runner.invoke(
        app,
        ["live-research-workflow-execution-records", "--home", str(tmp_path), "--json"],
    )
    library_payload = ZeusAgent(home=tmp_path).live_research_workflow_execution_record(
        status.to_payload(),
        record_ref="research-workflow-execution-record://wave188/library",
    )
    library_list = ZeusAgent(home=tmp_path).live_research_workflow_execution_records()

    assert completed.exit_code == 0, completed.stdout
    assert listed.exit_code == 0, listed.stdout
    completed_payload = json.loads(completed.stdout)
    listed_payload = json.loads(listed.stdout)
    assert completed_payload["execution_kind"] == "external"
    assert completed_payload["external_network_seen"] is True
    assert listed_payload["external_execution_record_count"] == 1
    assert library_payload["decision"] == "recorded"
    assert library_list["external_execution_record_count"] == 2
    assert library_list["network_opened"] is False


def _external_status(tag: str):
    return LiveResearchWorkflowExecutionStatusRuntime().build(
        external_execution=_ready_external_execution("registry-{0}".format(tag)),
        status_ref="research-workflow-execution-status://wave188/{0}".format(tag),
        evidence_ref="evidence://wave188/{0}".format(tag),
    )
