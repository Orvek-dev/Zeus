from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_external_transport_runtime import LiveResearchExternalTransportRuntime
from zeus_agent.live_research_workflow_evidence_graph_runtime import (
    LiveResearchWorkflowEvidenceGraphRuntime,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionRuntime,
)
from tests.test_wave141_live_research_external_transport import _client_result
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave185_live_research_workflow_external_execution import _preflight


def test_workflow_evidence_graph_binds_external_execution_to_graph() -> None:
    execution, external_result = _execution_and_external("ready")

    result = LiveResearchWorkflowEvidenceGraphRuntime().build(
        workflow_external_execution=execution,
        external_result=external_result,
        graph_ref="research-workflow-graph://wave189/ready",
        objective_id="wave189.objective",
    )

    assert result.decision == "workflow_graph_ready"
    assert result.graph_id is not None
    assert result.workflow_external_execution_bound is True
    assert result.external_result_bound is True
    assert result.graph_result_bound is True
    assert result.graph_created is True
    assert result.graph_node_count == 1
    assert result.external_network_seen is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_workflow_evidence_graph_blocks_transport_mismatch() -> None:
    execution, _external_result = _execution_and_external("mismatch")
    other_external = LiveResearchExternalTransportRuntime().execute(
        policy=_research_policy(),
        client_result=_client_result(),
        execution_ref="research-external://wave189/other",
    )

    result = LiveResearchWorkflowEvidenceGraphRuntime().build(
        workflow_external_execution=execution,
        external_result=other_external,
        graph_ref="research-workflow-graph://wave189/mismatch",
        objective_id="wave189.objective",
    )

    assert result.decision == "blocked"
    assert "research_workflow_graph_external_transport_mismatch" in result.blocked_reasons
    assert result.graph_result_bound is False
    assert result.network_opened is False


def test_workflow_evidence_graph_cli_and_library_surface_match() -> None:
    execution, external_result = _execution_and_external("cli")
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-workflow-evidence-graph",
            "--workflow-external-execution-json",
            execution.model_dump_json(),
            "--external-result-json",
            external_result.model_dump_json(),
            "--graph-ref",
            "research-workflow-graph://wave189/cli",
            "--objective-id",
            "wave189.objective",
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    library_payload = ZeusAgent().live_research_workflow_evidence_graph(
        workflow_external_execution=execution.to_payload(),
        external_result=external_result.to_payload(),
        graph_ref="research-workflow-graph://wave189/cli",
        objective_id="wave189.objective",
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "workflow_graph_ready"
    assert cli_payload["network_opened"] is False


def _execution_and_external(tag: str):
    policy = _research_policy()
    preflight = _preflight("workflow-graph-{0}".format(tag), policy=policy)
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=policy,
        client_result=_client_result(),
        execution_ref=preflight.external_execution_ref or "",
    )
    execution = LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        external_result=external_result,
        execution_record_ref="research-workflow-external-execution://wave189/{0}".format(tag),
    )
    return execution, external_result
