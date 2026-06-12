from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptRuntime


def test_approval_receipt_records_local_optin_proof_without_authority_grant() -> None:
    result = ApprovalReceiptRuntime().record(
        approval_id="provider-live",
        principal_id="operator.local",
        objective_id="wave58.objective",
        capability_id="provider.external.generate",
        now=datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc),
    )

    assert result.decision == "recorded"
    assert result.approval_receipt_recorded is True
    assert result.authority_granted is False
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.selected_gate is not None
    assert result.selected_gate["risk_kind"] == "external_provider_network"
    assert result.receipt_id.startswith("approval-receipt-")
    assert result.proof_hash.startswith("sha256:")
    assert result.issued_at == "2026-06-04T12:00:00+00:00"
    assert result.expires_at == "2026-06-04T12:30:00+00:00"


def test_approval_receipt_blocks_capability_scope_mismatch() -> None:
    result = ApprovalReceiptRuntime().record(
        approval_id="provider-live",
        principal_id="operator.local",
        objective_id="wave58.objective",
        capability_id="gateway.deliver",
    )

    assert result.decision == "blocked"
    assert result.approval_receipt_recorded is False
    assert result.authority_granted is False
    assert result.blocked_reasons == ("capability_scope_mismatch",)
    assert result.live_transport_enabled is False
    assert result.network_opened is False


def test_approval_receipt_blocks_unknown_gate() -> None:
    result = ApprovalReceiptRuntime().record(
        approval_id="unknown",
        principal_id="operator.local",
        objective_id="wave58.objective",
        capability_id="provider.external.generate",
    )

    assert result.decision == "blocked"
    assert result.selected_gate is None
    assert result.blocked_reasons == ("unknown_approval_gate",)
    assert result.approval_receipt_recorded is False
    assert result.no_secret_echo is True


def test_approval_receipt_redacts_secret_like_fields() -> None:
    raw_secret = "sk-" + "wave58-secret"
    result = ApprovalReceiptRuntime().record(
        approval_id="provider-live",
        principal_id="operator {0}".format(raw_secret),
        objective_id="wave58.objective",
        capability_id="provider.external.generate",
    )
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "secret_like_receipt_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True
    assert result.credential_material_accessed is False


def test_cli_exposes_approval_receipt_status() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "approval-receipt",
            "--approval-id",
            "provider-live",
            "--principal-id",
            "operator.local",
            "--objective-id",
            "wave58.objective",
            "--capability-id",
            "provider.external.generate",
            "--now",
            "2026-06-04T12:00:00+00:00",
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "recorded"
    assert payload["approval_receipt_recorded"] is True
    assert payload["authority_granted"] is False
    assert payload["selected_gate"]["approval_id"] == "provider-live"
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_approval_receipt_status() -> None:
    payload = ZeusAgent().approval_receipt_status(
        approval_id="external-delivery",
        principal_id="operator.local",
        objective_id="wave58.objective",
        capability_id="gateway.webhook.dispatch",
    )

    assert payload["decision"] == "recorded"
    assert payload["selected_gate"]["approval_id"] == "external-delivery"
    assert payload["approval_receipt_recorded"] is True
    assert payload["authority_granted"] is False
