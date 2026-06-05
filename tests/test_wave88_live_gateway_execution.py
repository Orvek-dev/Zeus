from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_gateway_execution_runtime import LiveGatewayExecutionRuntime


def test_live_gateway_dispatch_blocks_without_ready_envelope() -> None:
    result = LiveGatewayExecutionRuntime().dispatch(
        readiness=None,
        adapter_id="slack",
        target="slack://ops",
        message="status update",
    )

    assert result.decision == "blocked"
    assert "execution_readiness_required" in result.blocked_reasons
    assert result.delivery_planned is False
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_gateway_dispatch_plans_allowlisted_target_without_delivery() -> None:
    result = LiveGatewayExecutionRuntime().dispatch(
        readiness=_gateway_readiness(),
        adapter_id="slack",
        target="slack://ops",
        message="status update",
    )

    assert result.decision == "planned"
    assert result.delivery_planned is True
    assert result.dispatch_id is not None
    assert result.target_allowlisted is True
    assert result.external_delivery_opened is False
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_live_gateway_dispatch_blocks_unallowlisted_delivery() -> None:
    result = LiveGatewayExecutionRuntime().dispatch(
        readiness=_gateway_readiness(),
        adapter_id="email",
        target="https://example.invalid/hook",
        message="status update",
    )

    assert result.decision == "blocked"
    assert "unsupported_gateway_adapter" in result.blocked_reasons
    assert "delivery_target_not_allowlisted" in result.blocked_reasons
    assert result.delivery_planned is False
    assert result.external_delivery_opened is False


def test_cli_and_python_library_live_gateway_dispatch() -> None:
    readiness = _gateway_readiness()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-gateway-dispatch",
            "--readiness-json",
            readiness.model_dump_json(),
            "--adapter-id",
            "slack",
            "--target",
            "slack://ops",
            "--message",
            "status update",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "planned"
    assert payload["delivery_planned"] is True
    assert payload["external_delivery_opened"] is False

    library_payload = ZeusAgent().live_gateway_dispatch(
        readiness.to_payload(),
        adapter_id="slack",
        target="slack://ops",
        message="status update",
    )
    assert library_payload["decision"] == "planned"
    assert library_payload["network_opened"] is False


def _gateway_readiness() -> LiveExecutionReadinessResult:
    return LiveExecutionReadinessResult(
        decision="ready_for_external_operator",
        readiness_id="wave88.readiness.gateway",
        execution_plan_id="live-execute-plan-wave88",
        handoff_manifest_id="live-handoff-wave88",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.slack.dispatch",
        credential_bindings_ready=True,
        gateway_pairing_ready=True,
        secret_resolver_ready=True,
        operator_proof_bound=True,
        blocked_reasons=(),
        gate_summary={
            "credential_bindings_ready": True,
            "gateway_pairing_ready": True,
            "gateway_paired_target_count": 1,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        operator_proof_summary={
            "proof_id": "wave88.proof.operator",
            "operator_reviewed": True,
            "execution_authorized": False,
        },
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
