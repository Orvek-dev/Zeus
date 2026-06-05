from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptRuntime
from zeus_agent.cli import app
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessRuntime
from zeus_agent.live_execute_runtime import LiveExecutePlanRequest, LiveExecutePlanRuntime
from zeus_agent.live_handoff_runtime import LiveHandoffRequest, LiveHandoffRuntime
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.setup_runtime import setup_apply


def test_execution_readiness_blocks_unreviewed_execute_plan(tmp_path: Path) -> None:
    handoff = _ready_handoff(tmp_path)
    plan = LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave85.execution.gateway",
            handoff=handoff,
        ),
    )

    result = LiveExecutionReadinessRuntime().evaluate(plan)

    assert result.decision == "blocked"
    assert "operator_proof_required" in result.blocked_reasons
    assert result.operator_proof_bound is False
    assert result.execution_allowed is False
    assert result.live_transport_enabled is False
    assert result.live_production_claimed is False


def test_execution_readiness_accepts_proofed_execute_plan_without_granting_authority(
    tmp_path: Path,
) -> None:
    plan = _proofed_execute_plan(tmp_path)

    result = LiveExecutionReadinessRuntime().evaluate(plan)

    assert result.decision == "ready_for_external_operator"
    assert result.readiness_id is not None
    assert result.operator_proof_bound is True
    assert result.credential_bindings_ready is True
    assert result.gateway_pairing_ready is True
    assert result.secret_resolver_ready is True
    assert result.execution_allowed is False
    assert result.authority_granted is False
    assert result.network_opened is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_cli_and_python_library_execution_readiness(tmp_path: Path) -> None:
    plan = _proofed_execute_plan(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-execution-readiness",
            "--execute-plan-json",
            plan.model_dump_json(),
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "ready_for_external_operator"
    assert payload["operator_proof_bound"] is True
    assert payload["execution_allowed"] is False

    library_payload = ZeusAgent().live_execution_readiness(plan.to_payload())
    assert library_payload["decision"] == "ready_for_external_operator"
    assert library_payload["live_transport_enabled"] is False


def _proofed_execute_plan(home: Path):
    handoff = _ready_handoff(home)
    proof = LiveOperatorProofRuntime().record(
        proof_id="wave85.proof.operator",
        operator_id="wave85.operator",
        handoff_manifest_id=handoff.manifest_id,
        execution_plan_id="live-execute-plan-wave85",
        proof_ref="operator-proof://wave85/review",
        reviewed_risks=("secret_material_access", "external_delivery"),
    )
    return LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave85.execution.gateway",
            handoff=handoff,
            operator_proof=proof.to_payload(),
        ),
    )


def _ready_handoff(home: Path):
    _seed_gateway_setup(home)
    CredentialReadinessRuntime(home).bind(
        surface_kind="gateway",
        surface_id="slack",
        credential_scope="external.gateway.readonly",
        vault_ref="vault://zeus/external/gateway/readonly/slack",
    )
    GatewayPairingRuntime(home).pair(
        adapter_id="slack",
        target="slack://ops",
        proof_ref="pairing://slack/ops",
    )
    receipt = ApprovalReceiptRuntime().record(
        approval_id="external-delivery",
        principal_id="wave85.principal.operator",
        objective_id="wave85.objective.live",
        capability_id="gateway.webhook.dispatch",
        now=_now(),
    )
    preflight = LivePreflightRuntime(home=home).evaluate(
        _gateway_preflight(
            approval_receipt_id=receipt.receipt_id,
            approval_proof_hash=receipt.proof_hash,
        ),
        lease=_gateway_lease(),
        now=_now(),
    )
    return LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave85.handoff.gateway",
            lease_id="wave85.lease.live",
            preflight=preflight,
        ),
    )


def _seed_gateway_setup(home: Path) -> None:
    setup_apply(
        home=home,
        provider_id="local-llm",
        gateway=True,
        gateway_adapter="slack",
        gateway_target="slack://ops",
        local=True,
    )


def _gateway_preflight(
    *,
    approval_receipt_id: str | None,
    approval_proof_hash: str | None,
) -> LivePreflightRequest:
    return LivePreflightRequest(
        preflight_id="wave85.preflight.gateway",
        approval_id="external-delivery",
        principal_id="wave85.principal.operator",
        objective_id="wave85.objective.live",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.webhook.dispatch",
        evidence_target="mneme.wave85.live_execution_readiness",
        credential_scope="external.gateway.readonly",
        network_host="gateway.local",
        approval_receipt_id=approval_receipt_id,
        approval_proof_hash=approval_proof_hash,
        probe_healthy=True,
        source_pinned=False,
        delivery_target="slack://ops",
        allowlisted_delivery_targets=("slack://ops",),
        cleanup_required=True,
    )


def _gateway_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave85.lease.live",
        objective_id="wave85.objective.live",
        principal_id="wave85.principal.operator",
        run_id="wave85.run.live",
        allowed_capabilities=("gateway.webhook.dispatch",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave85.live_execution_readiness",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
