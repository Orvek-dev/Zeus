from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult, ApprovalReceiptRuntime
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.live_execute_runtime import LiveExecutePlanRequest, LiveExecutePlanRuntime
from zeus_agent.live_handoff_runtime import LiveHandoffRequest, LiveHandoffRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.setup_runtime import setup_apply


def test_live_handoff_carries_preflight_gate_summary(tmp_path: Path) -> None:
    preflight = _ready_gateway_preflight(tmp_path)

    handoff = LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave82.handoff.gateway",
            lease_id="wave82.lease.live",
            preflight=preflight,
        ),
    )

    assert handoff.decision == "handoff_ready"
    assert handoff.preflight_gate_summary["credential_bindings_ready"] is True
    assert handoff.preflight_gate_summary["credential_required_binding_count"] == 1
    assert handoff.preflight_gate_summary["credential_ready_binding_count"] == 1
    assert handoff.preflight_gate_summary["gateway_pairing_ready"] is True
    assert handoff.preflight_gate_summary["gateway_paired_target_count"] == 1
    assert handoff.preflight_gate_summary["credential_material_accessed"] is False
    assert handoff.preflight_gate_summary["proof_material_accessed"] is False
    assert handoff.preflight_gate_summary["network_opened"] is False
    assert handoff.live_production_claimed is False


def test_live_execute_plan_carries_handoff_gate_summary(tmp_path: Path) -> None:
    preflight = _ready_gateway_preflight(tmp_path)
    handoff = LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave82.handoff.gateway",
            lease_id="wave82.lease.live",
            preflight=preflight,
        ),
    )

    plan = LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave82.execution.gateway",
            handoff=handoff,
        ),
    )

    assert plan.decision == "planned"
    assert plan.handoff_gate_summary["credential_bindings_ready"] is True
    assert plan.handoff_gate_summary["gateway_pairing_ready"] is True
    assert plan.handoff_gate_summary["gateway_paired_target_count"] == 1
    assert plan.handoff_gate_summary["credential_material_accessed"] is False
    assert plan.handoff_gate_summary["proof_material_accessed"] is False
    assert plan.network_opened is False
    assert plan.external_delivery_opened is False
    assert plan.live_production_claimed is False


def _ready_gateway_preflight(home: Path):
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
    receipt = _receipt()
    return LivePreflightRuntime(home=home).evaluate(
        _gateway_preflight(
            approval_receipt_id=receipt.receipt_id,
            approval_proof_hash=receipt.proof_hash,
        ),
        lease=_gateway_lease(),
        now=_now(),
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
        preflight_id="wave82.preflight.gateway",
        approval_id="external-delivery",
        principal_id="wave82.principal.operator",
        objective_id="wave82.objective.live",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.webhook.dispatch",
        evidence_target="mneme.wave82.live_handoff",
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


def _receipt() -> ApprovalReceiptResult:
    return ApprovalReceiptRuntime().record(
        approval_id="external-delivery",
        principal_id="wave82.principal.operator",
        objective_id="wave82.objective.live",
        capability_id="gateway.webhook.dispatch",
        now=_now(),
    )


def _gateway_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave82.lease.live",
        objective_id="wave82.objective.live",
        principal_id="wave82.principal.operator",
        run_id="wave82.run.live",
        allowed_capabilities=("gateway.webhook.dispatch",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave82.live_handoff",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
