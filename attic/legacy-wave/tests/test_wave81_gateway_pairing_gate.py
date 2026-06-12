from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult, ApprovalReceiptRuntime
from zeus_agent.cli import app
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.live_dry_run_runtime import LiveDryRunRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.setup_runtime import setup_apply


def test_gateway_pairing_runtime_records_reference_only_pairing(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)

    paired = GatewayPairingRuntime(tmp_path).pair(
        adapter_id="slack",
        target="slack://ops",
        proof_ref="pairing://slack/ops",
    )
    listed = GatewayPairingRuntime(tmp_path).list()

    assert paired.decision == "paired"
    assert paired.pairing is not None
    assert paired.pairing["adapter_id"] == "slack"
    assert paired.pairing["target"] == "slack://ops"
    assert paired.pairing["pairing_configured"] is True
    assert listed.paired_target_count == 1
    assert listed.pairings[0]["proof_ref"] == "pairing://slack/ops"
    assert listed.network_opened is False
    assert listed.credential_material_accessed is False
    assert listed.external_delivery_opened is False
    assert listed.live_production_claimed is False


def test_gateway_pairing_blocks_secret_like_proof_refs(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    raw_secret = "sk-" + "wave81-secret"

    result = GatewayPairingRuntime(tmp_path).pair(
        adapter_id="slack",
        target="slack://ops",
        proof_ref=raw_secret,
    )
    listed = GatewayPairingRuntime(tmp_path).list()
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    assert result.decision == "blocked"
    assert result.blocked_reasons == ("unsafe_pairing_proof_ref",)
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert listed.paired_target_count == 0
    assert result.no_secret_echo is True


def test_gateway_cli_can_pair_and_show_configured_target(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    runner = CliRunner()

    paired = runner.invoke(
        app,
        [
            "gateway",
            "--pair",
            "slack",
            "--target",
            "slack://ops",
            "--pairing-proof-ref",
            "pairing://slack/ops",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    listed = runner.invoke(app, ["gateway", "--list-config", "--home", str(tmp_path), "--json"])

    assert paired.exit_code == 0, paired.stdout
    assert listed.exit_code == 0, listed.stdout
    paired_payload = json.loads(paired.stdout)
    listed_payload = json.loads(listed.stdout)
    assert paired_payload["decision"] == "paired"
    assert paired_payload["pairing"]["pairing_configured"] is True
    assert listed_payload["configured_targets"][0]["pairing_configured"] is True
    assert listed_payload["gateway_paired"] is True
    assert listed_payload["network_opened"] is False


def test_live_preflight_blocks_gateway_when_pairing_missing(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    _bind_gateway_credential(tmp_path)
    receipt = _receipt()

    result = LivePreflightRuntime(home=tmp_path).evaluate(
        _gateway_preflight(
            approval_receipt_id=receipt.receipt_id,
            approval_proof_hash=receipt.proof_hash,
        ),
        lease=_gateway_lease(),
        now=_now(),
    )

    assert result.decision == "blocked"
    assert result.credential_bindings_ready is True
    assert result.gateway_pairing_ready is False
    assert "gateway_pairing_not_ready" in result.blocked_reasons
    assert result.gateway_pairing is not None
    assert result.gateway_pairing["paired_target_count"] == 0
    assert result.network_opened is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_preflight_accepts_gateway_pairing_proof(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    _bind_gateway_credential(tmp_path)
    GatewayPairingRuntime(tmp_path).pair(
        adapter_id="slack",
        target="slack://ops",
        proof_ref="pairing://slack/ops",
    )
    receipt = _receipt()

    result = LivePreflightRuntime(home=tmp_path).evaluate(
        _gateway_preflight(
            approval_receipt_id=receipt.receipt_id,
            approval_proof_hash=receipt.proof_hash,
        ),
        lease=_gateway_lease(),
        now=_now(),
    )

    assert result.decision == "preflight_ready"
    assert result.credential_bindings_ready is True
    assert result.gateway_pairing_ready is True
    assert result.gateway_pairing is not None
    assert result.gateway_pairing["paired_target_count"] == 1
    assert result.live_beta_ready is True
    assert result.authority_granted is False


def test_live_dry_run_check_credentials_requires_gateway_pairing(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    _bind_gateway_credential(tmp_path)

    result = LiveDryRunRuntime(home=tmp_path).run(
        surface_id="gateway.slack",
        principal_id="wave81.principal.operator",
        objective_id="wave81.objective.live",
        now=_now(),
        check_credentials=True,
    )

    assert result.decision == "blocked"
    assert "preflight:gateway_pairing_not_ready" in result.blocked_reasons
    assert result.preflight is not None
    assert result.preflight.gateway_pairing_ready is False
    assert result.network_opened is False


def test_python_library_gateway_pairing_allows_dry_run(tmp_path: Path) -> None:
    agent = ZeusAgent(home=tmp_path)
    _seed_gateway_setup(tmp_path)
    _bind_gateway_credential(tmp_path)

    paired = agent.gateway_pair(adapter_id="slack", target="slack://ops", proof_ref="pairing://slack/ops")
    payload = agent.live_dry_run(
        surface_id="gateway.slack",
        principal_id="wave81.principal.operator",
        objective_id="wave81.objective.live",
        now=_now(),
        check_credentials=True,
    )

    assert paired["decision"] == "paired"
    assert payload["decision"] == "planned"
    assert payload["preflight"]["gateway_pairing_ready"] is True
    assert payload["execute_plan"]["decision"] == "planned"
    assert payload["external_delivery_opened"] is False


def _seed_gateway_setup(home: Path) -> None:
    setup_apply(
        home=home,
        provider_id="local-llm",
        gateway=True,
        gateway_adapter="slack",
        gateway_target="slack://ops",
        local=True,
    )


def _bind_gateway_credential(home: Path) -> None:
    CredentialReadinessRuntime(home).bind(
        surface_kind="gateway",
        surface_id="slack",
        credential_scope="external.gateway.readonly",
        vault_ref="vault://zeus/external/gateway/readonly/slack",
    )


def _gateway_preflight(
    *,
    approval_receipt_id: str | None,
    approval_proof_hash: str | None,
) -> LivePreflightRequest:
    return LivePreflightRequest(
        preflight_id="wave81.preflight.gateway",
        approval_id="external-delivery",
        principal_id="wave81.principal.operator",
        objective_id="wave81.objective.live",
        surface_kind="gateway",
        surface_id="gateway.slack",
        capability_id="gateway.webhook.dispatch",
        evidence_target="mneme.wave81.live_preflight",
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
        principal_id="wave81.principal.operator",
        objective_id="wave81.objective.live",
        capability_id="gateway.webhook.dispatch",
        now=_now(),
    )


def _gateway_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave81.lease.live",
        objective_id="wave81.objective.live",
        principal_id="wave81.principal.operator",
        run_id="wave81.run.live",
        allowed_capabilities=("gateway.webhook.dispatch",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave81.live_preflight",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
