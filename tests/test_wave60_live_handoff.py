from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptRuntime
from zeus_agent.live_handoff_runtime import LiveHandoffRequest, LiveHandoffRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease


def test_live_handoff_creates_reviewable_manifest_from_ready_preflight() -> None:
    preflight = _ready_preflight()

    result = LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave60.handoff.provider",
            lease_id="wave60.lease.live",
            preflight=preflight,
        ),
    )

    assert result.decision == "handoff_ready"
    assert result.manifest_id.startswith("live-handoff-")
    assert result.preflight_id == "wave60.preflight.provider"
    assert result.approval_receipt_id == preflight.approval_receipt.receipt_id
    assert result.operator_review_required is True
    assert result.execution_allowed is False
    assert result.authority_granted is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_handoff_blocks_non_ready_preflight() -> None:
    preflight = _blocked_preflight()

    result = LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave60.handoff.provider",
            lease_id="wave60.lease.live",
            preflight=preflight,
        ),
    )

    assert result.decision == "blocked"
    assert "preflight_not_ready" in result.blocked_reasons
    assert result.execution_allowed is False
    assert result.manifest_id is None
    assert result.network_opened is False


def test_live_handoff_blocks_production_release_request() -> None:
    preflight = _ready_preflight()

    result = LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave60.handoff.provider",
            lease_id="wave60.lease.live",
            preflight=preflight,
            production_release_requested=True,
        ),
    )

    assert result.decision == "blocked"
    assert "production_release_forbidden" in result.blocked_reasons
    assert result.execution_allowed is False
    assert result.live_production_claimed is False


def test_live_handoff_redacts_secret_like_operator_note() -> None:
    raw_secret = "sk-" + "wave60-secret"
    preflight = _ready_preflight()

    result = LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave60.handoff.provider",
            lease_id="wave60.lease.live",
            preflight=preflight,
            operator_note="note {0}".format(raw_secret),
        ),
    )
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "secret_like_handoff_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True


def test_cli_exposes_live_handoff_manifest() -> None:
    preflight = _ready_preflight()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-handoff",
            "--request-json",
            LiveHandoffRequest(
                handoff_id="wave60.handoff.provider",
                lease_id="wave60.lease.live",
                preflight=preflight,
            ).model_dump_json(),
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "handoff_ready"
    assert payload["operator_review_required"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_live_handoff_manifest() -> None:
    preflight = _ready_preflight()
    payload = ZeusAgent().live_handoff(
        LiveHandoffRequest(
            handoff_id="wave60.handoff.provider",
            lease_id="wave60.lease.live",
            preflight=preflight,
        ),
    )

    assert payload["decision"] == "handoff_ready"
    assert payload["execution_allowed"] is False
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def _ready_preflight():
    receipt = ApprovalReceiptRuntime().record(
        approval_id="provider-live",
        principal_id="wave60.principal.operator",
        objective_id="wave60.objective.live",
        capability_id="provider.external.generate",
        now=_now(),
    )
    request = LivePreflightRequest(
        preflight_id="wave60.preflight.provider",
        approval_id="provider-live",
        principal_id="wave60.principal.operator",
        objective_id="wave60.objective.live",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        evidence_target="mneme.wave60.live_handoff",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
        probe_healthy=True,
        source_pinned=True,
        cleanup_required=True,
    )
    return LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())


def _blocked_preflight():
    receipt = ApprovalReceiptRuntime().record(
        approval_id="provider-live",
        principal_id="wave60.principal.operator",
        objective_id="wave60.objective.live",
        capability_id="provider.external.generate",
        now=_now(),
    )
    request = LivePreflightRequest(
        preflight_id="wave60.preflight.provider",
        approval_id="provider-live",
        principal_id="wave60.principal.operator",
        objective_id="wave60.objective.live",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        evidence_target="mneme.wave60.live_handoff",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
        probe_healthy=True,
        source_pinned=False,
        cleanup_required=True,
    )
    return LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())


def _lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave60.lease.live",
        objective_id="wave60.objective.live",
        principal_id="wave60.principal.operator",
        run_id="wave60.run.live",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=100,
        evidence_target="mneme.wave60.live_handoff",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
