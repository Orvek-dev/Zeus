from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportRuntime
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusRuntime,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionRuntime,
)
from tests.test_wave141_live_research_external_transport import _client_result
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave185_live_research_workflow_external_execution import _preflight


def test_research_workflow_execution_status_records_external_execution() -> None:
    execution = _ready_external_execution("status")

    result = LiveResearchWorkflowExecutionStatusRuntime().build(
        external_execution=execution,
        status_ref="research-workflow-execution-status://wave187/recorded",
        evidence_ref="evidence://wave187/recorded",
    )

    assert result.decision == "execution_recorded"
    assert result.status_id is not None
    assert result.execution_kind == "external"
    assert result.workflow_execution_id == execution.execution_id
    assert result.external_execution_bound is True
    assert result.loopback_executor_bound is False
    assert result.external_execution_id == execution.execution_id
    assert result.external_transport_execution_id == execution.external_transport_execution_id
    assert result.external_network_seen is True
    assert result.external_non_loopback_network_seen is True
    assert result.non_loopback_network_opened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_research_workflow_execution_status_blocks_missing_external_evidence_and_ambiguous_source() -> None:
    execution = _blocked_external_execution()
    loopback_status = LiveResearchWorkflowExecutionStatusRuntime().build(
        external_execution=execution,
        status_ref="research-workflow-execution-status://wave187/blocked",
        evidence_ref="",
    )
    ambiguous = LiveResearchWorkflowExecutionStatusRuntime().build(
        loopback_executor=_fake_loopback_payload(),
        external_execution=_ready_external_execution("ambiguous"),
        status_ref="research-workflow-execution-status://wave187/ambiguous",
        evidence_ref="evidence://wave187/ambiguous",
    )

    assert loopback_status.decision == "blocked"
    assert "evidence_ref_required" in loopback_status.blocked_reasons
    assert "research_workflow_external_execution_not_recorded" in loopback_status.blocked_reasons
    assert loopback_status.network_opened is False
    assert ambiguous.decision == "blocked"
    assert "research_workflow_execution_source_ambiguous" in ambiguous.blocked_reasons


def test_research_workflow_execution_status_external_cli_library_and_cockpit_surface() -> None:
    execution = _ready_external_execution("cli")
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-execution-status",
            "--external-execution-json",
            execution.model_dump_json(),
            "--status-ref",
            "research-workflow-execution-status://wave187/cli",
            "--evidence-ref",
            "evidence://wave187/cli",
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    library_payload = ZeusAgent().live_research_workflow_execution_status(
        external_execution=execution.to_payload(),
        status_ref="research-workflow-execution-status://wave187/cli",
        evidence_ref="evidence://wave187/cli",
    )
    cockpit = LiveCockpitRuntime().build(
        research_workflow_execution_status=LiveResearchWorkflowExecutionStatusRuntime().build(
            external_execution=execution,
            status_ref="research-workflow-execution-status://wave187/cockpit",
            evidence_ref="evidence://wave187/cockpit",
        )
    )

    assert cli_payload == library_payload
    assert cli_payload["decision"] == "execution_recorded"
    assert cli_payload["execution_kind"] == "external"
    assert cli_payload["external_network_seen"] is True
    assert cockpit.research_workflow_execution_status_external_network_seen is True
    assert cockpit.research_workflow_execution_status_external_non_loopback_network_seen is True
    assert cockpit.network_opened is False


def _ready_external_execution(tag: str):
    policy = _research_policy()
    preflight = _preflight("status-{0}".format(tag), policy=policy)
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=policy,
        client_result=_client_result(),
        execution_ref=preflight.external_execution_ref or "",
    )
    return LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        external_result=external_result,
        execution_record_ref="research-workflow-external-execution://wave187/{0}".format(tag),
    )


def _blocked_external_execution():
    policy = _research_policy()
    return LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=_preflight("status-blocked", policy=policy),
        execution_record_ref="research-workflow-external-execution://wave187/blocked",
    )


def _fake_loopback_payload():
    from tests.test_wave178_live_cockpit_research_workflow_loopback_executor import _executed_loopback

    return _executed_loopback()
