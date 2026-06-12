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
from zeus_agent.live_execute_runtime import LiveExecutePlanRequest, LiveExecutePlanRuntime
from zeus_agent.live_handoff_runtime import LiveHandoffRequest, LiveHandoffRuntime
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.setup_runtime import setup_apply


def test_live_operator_proof_records_reference_only_review() -> None:
    result = LiveOperatorProofRuntime().record(
        proof_id="wave84.proof.operator",
        operator_id="wave84.operator",
        handoff_manifest_id="live-handoff-wave84",
        execution_plan_id="live-execute-plan-wave84",
        proof_ref="operator-proof://wave84/review",
        reviewed_risks=("secret_material_access", "external_delivery"),
    )

    assert result.decision == "recorded"
    assert result.proof_hash is not None
    assert result.operator_reviewed is True
    assert result.execution_authorized is False
    assert result.material_access_authorized is False
    assert result.network_authorized is False
    assert result.external_delivery_authorized is False
    assert result.proof_material_accessed is False
    assert result.no_secret_echo is True


def test_live_execute_plan_carries_operator_proof_summary(tmp_path: Path) -> None:
    handoff = _ready_handoff(tmp_path)
    proof = LiveOperatorProofRuntime().record(
        proof_id="wave84.proof.operator",
        operator_id="wave84.operator",
        handoff_manifest_id=handoff.manifest_id,
        execution_plan_id="live-execute-plan-wave84",
        proof_ref="operator-proof://wave84/review",
        reviewed_risks=("secret_material_access", "external_delivery"),
    )

    plan = LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave84.execution.gateway",
            handoff=handoff,
            operator_proof=proof.to_payload(),
        ),
    )

    assert plan.decision == "planned"
    assert plan.operator_proof_bound is True
    assert plan.operator_proof_summary is not None
    assert plan.operator_proof_summary["proof_id"] == "wave84.proof.operator"
    assert plan.operator_proof_summary["operator_reviewed"] is True
    assert plan.operator_proof_summary["execution_authorized"] is False
    assert plan.execution_allowed is False
    assert plan.authority_granted is False
    assert plan.live_transport_enabled is False


def test_cli_and_python_library_live_operator_proof() -> None:
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-operator-proof",
            "--proof-id",
            "wave84.proof.operator",
            "--operator-id",
            "wave84.operator",
            "--handoff-manifest-id",
            "live-handoff-wave84",
            "--execution-plan-id",
            "live-execute-plan-wave84",
            "--proof-ref",
            "operator-proof://wave84/review",
            "--reviewed-risk",
            "secret_material_access",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "recorded"
    assert payload["execution_authorized"] is False
    assert payload["proof_material_accessed"] is False

    library_payload = ZeusAgent().live_operator_proof(
        proof_id="wave84.proof.operator",
        operator_id="wave84.operator",
        handoff_manifest_id="live-handoff-wave84",
        execution_plan_id="live-execute-plan-wave84",
        proof_ref="operator-proof://wave84/review",
        reviewed_risks=("secret_material_access",),
    )
    assert library_payload["decision"] == "recorded"
    assert library_payload["network_authorized"] is False


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
        principal_id="wave84.principal.operator",
        objective_id="wave84.objective.live",
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
            handoff_id="wave84.handoff.gateway",
            lease_id="wave84.lease.live",
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
        preflight_id="wave84.preflight.gateway",
        approval_id="external-delivery",
        principal_id="wave84.principal.operator",
        objective_id="wave84.objective.live",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.webhook.dispatch",
        evidence_target="mneme.wave84.live_operator_proof",
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
        lease_id="wave84.lease.live",
        objective_id="wave84.objective.live",
        principal_id="wave84.principal.operator",
        run_id="wave84.run.live",
        allowed_capabilities=("gateway.webhook.dispatch",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave84.live_operator_proof",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
