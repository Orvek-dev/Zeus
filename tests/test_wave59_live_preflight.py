from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult, ApprovalReceiptRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease


def test_live_preflight_accepts_bound_receipt_lease_probe_source_and_cleanup() -> None:
    receipt = _receipt()
    request = _provider_preflight(
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
    )

    result = LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())

    assert result.decision == "preflight_ready"
    assert result.approval_receipt_bound is True
    assert result.lease_authorized is True
    assert result.cleanup_required is True
    assert result.activation_decision == "live_beta"
    assert result.live_beta_ready is True
    assert result.authority_granted is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_preflight_blocks_receipt_id_mismatch() -> None:
    receipt = _receipt()
    request = _provider_preflight(
        approval_receipt_id="approval-receipt-wrong",
        approval_proof_hash=receipt.proof_hash,
    )

    result = LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())

    assert result.decision == "blocked"
    assert "approval_receipt_id_mismatch" in result.blocked_reasons
    assert result.approval_receipt_bound is False
    assert result.live_beta_ready is False
    assert result.network_opened is False


def test_live_preflight_blocks_missing_cleanup_plan() -> None:
    receipt = _receipt()
    request = _provider_preflight(
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
        cleanup_required=False,
    )

    result = LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())

    assert result.decision == "blocked"
    assert "cleanup_plan_required" in result.blocked_reasons
    assert result.activation_decision == "live_beta"
    assert result.live_beta_ready is False


def test_live_preflight_blocks_activation_when_source_unpinned() -> None:
    receipt = _receipt()
    request = _provider_preflight(
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
        source_pinned=False,
    )

    result = LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())

    assert result.decision == "blocked"
    assert "activation:adapter_source_unpinned" in result.blocked_reasons
    assert result.activation_decision == "blocked"
    assert result.lease_authorized is True
    assert result.approval_receipt_bound is True


def test_live_preflight_redacts_secret_like_receipt_fields() -> None:
    raw_secret = "sk-" + "wave59-secret"
    request = _provider_preflight(
        principal_id="operator {0}".format(raw_secret),
        approval_receipt_id="approval-receipt-placeholder",
        approval_proof_hash="sha256:placeholder",
    )

    result = LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "approval_receipt_not_recorded" in result.blocked_reasons
    assert "secret_like_receipt_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True


def test_cli_exposes_live_preflight_contract() -> None:
    receipt = _receipt()
    request = _provider_preflight(
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-preflight",
            "--request-json",
            request.model_dump_json(),
            "--lease-json",
            _lease().model_dump_json(),
            "--now",
            _now().isoformat(),
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "preflight_ready"
    assert payload["approval_receipt_bound"] is True
    assert payload["activation_decision"] == "live_beta"
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_live_preflight_contract() -> None:
    receipt = _receipt()
    request = _provider_preflight(
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
    )

    payload = ZeusAgent().live_preflight(request, lease=_lease(), now=_now())

    assert payload["decision"] == "preflight_ready"
    assert payload["approval_receipt_bound"] is True
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def _provider_preflight(
    *,
    principal_id: str = "wave59.principal.operator",
    approval_receipt_id: str | None,
    approval_proof_hash: str | None,
    cleanup_required: bool = True,
    source_pinned: bool = True,
) -> LivePreflightRequest:
    return LivePreflightRequest(
        preflight_id="wave59.preflight.provider",
        approval_id="provider-live",
        principal_id=principal_id,
        objective_id="wave59.objective.live",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        evidence_target="mneme.wave59.live_preflight",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        approval_receipt_id=approval_receipt_id,
        approval_proof_hash=approval_proof_hash,
        probe_healthy=True,
        source_pinned=source_pinned,
        cleanup_required=cleanup_required,
    )


def _receipt() -> ApprovalReceiptResult:
    return ApprovalReceiptRuntime().record(
        approval_id="provider-live",
        principal_id="wave59.principal.operator",
        objective_id="wave59.objective.live",
        capability_id="provider.external.generate",
        now=_now(),
    )


def _lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave59.lease.live",
        objective_id="wave59.objective.live",
        principal_id="wave59.principal.operator",
        run_id="wave59.run.live",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=100,
        evidence_target="mneme.wave59.live_preflight",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
