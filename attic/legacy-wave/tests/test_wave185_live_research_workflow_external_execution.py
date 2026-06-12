from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_research_external_transport_runtime import (
    LiveResearchExternalTransportRuntime,
)
from zeus_agent.live_research_owned_client_transport_runtime import (
    LiveResearchOwnedClientTransportRuntime,
    StaticResearchOwnedClient,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionRuntime,
)
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightRuntime,
)
from tests.test_wave141_live_research_external_transport import _client_result
from tests.test_wave141_live_research_external_transport import _research_policy
from tests.test_wave148_live_research_owned_client_transport import _receipt
from tests.test_wave177_live_research_workflow_loopback_executor import _ready_handoff


def test_workflow_external_execution_records_preflight_bound_external_result() -> None:
    policy = _research_policy()
    preflight = _preflight("direct-external", policy=policy)
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=policy,
        client_result=_client_result(),
        execution_ref=preflight.external_execution_ref or "",
    )

    result = LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        external_result=external_result,
        execution_record_ref="research-workflow-external-execution://wave185/record",
    )

    assert result.decision == "external_execution_recorded"
    assert result.execution_id is not None
    assert result.workflow_external_preflight_bound is True
    assert result.external_result_bound is True
    assert result.policy_id == policy.policy_id
    assert result.source_id == "github"
    assert result.source_pin_bound is True
    assert result.external_transport_executed is True
    assert result.external_network_seen is True
    assert result.external_non_loopback_network_seen is True
    assert result.external_cleanup_receipt_bound is True
    assert result.network_opened is False
    assert result.live_transport_enabled is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False
    assert "ghp_" + "wave141" not in json.dumps(result.to_payload())
    assert result.no_secret_echo is True


def test_workflow_external_execution_accepts_owned_client_bridge() -> None:
    policy = _research_policy()
    preflight = _preflight("owned-client", policy=policy)
    owned_result = LiveResearchOwnedClientTransportRuntime().execute(
        policy=policy,
        client=StaticResearchOwnedClient(_receipt()),
        execution_ref=preflight.external_execution_ref or "",
    )

    result = LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        owned_client_result=owned_result,
        execution_record_ref="research-workflow-external-execution://wave185/owned",
    )

    assert result.decision == "external_execution_recorded"
    assert result.owned_client_result_bound is True
    assert result.external_result_bound is True
    assert result.owned_client_execution_id == owned_result.execution_id
    assert result.external_transport_execution_id == owned_result.external_transport_result.execution_id
    assert result.external_network_seen is True
    assert result.network_opened is False


def test_workflow_external_execution_blocks_missing_result_and_mismatched_ref() -> None:
    policy = _research_policy()
    preflight = _preflight("blocked", policy=policy)
    missing_result = LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        execution_record_ref="research-workflow-external-execution://wave185/missing",
    )
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=policy,
        client_result=_client_result(),
        execution_ref="research-external://wave185/wrong-ref",
    )
    mismatched = LiveResearchWorkflowExternalExecutionRuntime().record(
        preflight=preflight,
        external_result=external_result,
        execution_record_ref="research-workflow-external-execution://wave185/mismatch",
    )

    assert missing_result.decision == "blocked"
    assert "research_external_transport_result_required" in missing_result.blocked_reasons
    assert missing_result.network_opened is False
    assert mismatched.decision == "blocked"
    assert "research_external_execution_ref_mismatch" in mismatched.blocked_reasons
    assert mismatched.external_network_seen is True
    assert mismatched.network_opened is False


def test_workflow_external_execution_cli_and_library_surface_match() -> None:
    policy = _research_policy()
    preflight = _preflight("cli", policy=policy)
    external_result = LiveResearchExternalTransportRuntime().execute(
        policy=policy,
        client_result=_client_result(),
        execution_ref=preflight.external_execution_ref or "",
    )

    completed = CliRunner().invoke(
        app,
        [
            "live-research-workflow-external-execution",
            "--preflight-json",
            preflight.model_dump_json(),
            "--external-result-json",
            external_result.model_dump_json(),
            "--execution-record-ref",
            "research-workflow-external-execution://wave185/cli",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_research_workflow_external_execution(
        preflight=preflight.to_payload(),
        external_result=external_result.to_payload(),
        execution_record_ref="research-workflow-external-execution://wave185/cli",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload == library_payload
    assert cli_payload["decision"] == "external_execution_recorded"
    assert cli_payload["external_network_seen"] is True
    assert cli_payload["network_opened"] is False


def _preflight(tag: str, *, policy):
    return LiveResearchWorkflowExternalPreflightRuntime().build(
        handoff=_ready_handoff("external-execution-{0}".format(tag)),
        policy=policy,
        preflight_ref="research-workflow-external-preflight://wave185/{0}".format(tag),
        external_execution_ref="research-external://wave185/{0}".format(tag),
        operator_approval_ref=policy.approval_ref or "",
        evidence_ref="evidence://wave185/{0}".format(tag),
    )
