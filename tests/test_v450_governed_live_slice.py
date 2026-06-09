from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v450_release_gate_reports_governed_live_slice_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v4.5.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v4.5.0"
    assert payload["release_stage"] == "governed_live_slice_authority_ux"
    assert payload["governed_live_slice_contract_available"] is True
    assert payload["authority_ux_runtime_available"] is True
    assert payload["live_preflight_requirement_map_available"] is True
    assert payload["trusted_loopback_live_smoke_available"] is True
    assert payload["governed_live_slice_ready"] is True
    assert payload["production_ready"] is False
    assert payload["next_version"] is None


def test_governed_live_slice_blocks_missing_authority_with_operator_steps() -> None:
    agent = ZeusAgent()
    payload = agent.governed_live_slice(
        surface="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
    )

    assert payload["decision"] == "blocked"
    assert payload["surface"] == "provider"
    assert "lease.missing_lease" in payload["blocked_reasons"]
    assert "approval.missing_approval" in payload["blocked_reasons"]
    assert payload["missing_requirements"] == [
        "objective_run_id",
        "lease_ref",
        "approval_ref",
        "promotion_guard_ref",
        "broker_evidence_ref",
        "credential_scope",
        "sandbox_policy_ref",
        "audit_receipt_ref",
    ]
    assert payload["operator_next_steps"]
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False


def test_governed_live_slice_allows_trusted_local_smoke_through_broker_evidence() -> None:
    agent = ZeusAgent()
    payload = agent.governed_live_slice(
        surface="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        objective_run_id="run-v450",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
        sandbox_policy_ref="sandbox://local/default-deny-egress",
        audit_receipt_ref="audit://v450/provider-local-smoke",
    )

    assert payload["decision"] == "allowed"
    assert payload["handler_executed"] is True
    assert payload["broker_evidence_bound"] is True
    assert payload["broker_evidence_status"] == "pass"
    assert payload["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["live_production_claimed"] is False
    assert payload["operator_next_steps"] == []


def test_governed_live_slice_blocks_raw_secret_without_echo() -> None:
    raw_secret = "token=" + "sk" + "-v450-secret"
    agent = ZeusAgent()
    payload = agent.governed_live_slice(
        surface="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
        objective_run_id="run-v450",
        lease_ref="lease://v210/provider-local-smoke",
        approval_ref="approval://v210/provider-local-smoke",
        promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
        broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
        credential_scope="credential.local-smoke",
        sandbox_policy_ref="sandbox://local/default-deny-egress",
        audit_receipt_ref="audit://v450/provider-local-smoke",
        raw_credential=raw_secret,
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "blocked"
    assert "credential.raw_secret_raw_credential_blocked" in payload["blocked_reasons"]
    assert raw_secret not in serialized
    assert payload["no_secret_echo"] is True
    assert payload["handler_executed"] is False


def test_cli_governed_live_slice_matches_library_surface(tmp_path: Path) -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        [
            "governed-live-slice",
            "--surface",
            "provider",
            "--capability-id",
            "provider.local-smoke",
            "--scenario",
            "local-smoke",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).governed_live_slice(
        surface="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["decision"] == "blocked"
    assert cli_payload["missing_requirements"] == library_payload["missing_requirements"]
    assert cli_payload["handler_executed"] is False
