from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult, ApprovalReceiptRuntime
from zeus_agent.cli import app
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.setup_runtime import setup_apply


def test_live_preflight_blocks_when_home_credential_binding_is_missing(tmp_path: Path) -> None:
    _seed_mcp_setup(tmp_path)
    receipt = _receipt()

    result = LivePreflightRuntime(home=tmp_path).evaluate(
        _mcp_preflight(
            approval_receipt_id=receipt.receipt_id,
            approval_proof_hash=receipt.proof_hash,
        ),
        lease=_mcp_lease(),
        now=_now(),
    )

    assert result.decision == "blocked"
    assert "credential_binding_not_ready" in result.blocked_reasons
    assert result.credential_bindings_ready is False
    assert result.credential_readiness is not None
    assert result.credential_readiness["required_binding_count"] == 1
    assert result.credential_readiness["ready_binding_count"] == 0
    assert result.credential_material_accessed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_live_preflight_accepts_reference_bound_mcp_credential(tmp_path: Path) -> None:
    _seed_mcp_setup(tmp_path)
    CredentialReadinessRuntime(tmp_path).bind(
        surface_kind="mcp",
        surface_id="mcp.github",
        credential_scope="external.github.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_GITHUB_READONLY",
    )
    receipt = _receipt()

    result = LivePreflightRuntime(home=tmp_path).evaluate(
        _mcp_preflight(
            approval_receipt_id=receipt.receipt_id,
            approval_proof_hash=receipt.proof_hash,
        ),
        lease=_mcp_lease(),
        now=_now(),
    )

    assert result.decision == "preflight_ready"
    assert result.credential_bindings_ready is True
    assert result.credential_readiness is not None
    assert result.credential_readiness["ready_binding_count"] == 1
    assert result.live_beta_ready is True
    assert result.authority_granted is False
    assert result.live_transport_enabled is False
    assert result.credential_material_accessed is False


def test_cli_live_preflight_home_enables_credential_gate(tmp_path: Path) -> None:
    _seed_mcp_setup(tmp_path)
    receipt = _receipt()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-preflight",
            "--request-json",
            _mcp_preflight(
                approval_receipt_id=receipt.receipt_id,
                approval_proof_hash=receipt.proof_hash,
            ).model_dump_json(),
            "--lease-json",
            _mcp_lease().model_dump_json(),
            "--home",
            str(tmp_path),
            "--now",
            _now().isoformat(),
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "blocked"
    assert "credential_binding_not_ready" in payload["blocked_reasons"]
    assert payload["credential_bindings_ready"] is False
    assert payload["network_opened"] is False


def test_python_library_live_preflight_can_opt_into_credential_gate(tmp_path: Path) -> None:
    _seed_mcp_setup(tmp_path)
    CredentialReadinessRuntime(tmp_path).bind(
        surface_kind="mcp",
        surface_id="mcp.github",
        credential_scope="external.github.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_GITHUB_READONLY",
    )
    receipt = _receipt()

    payload = ZeusAgent(home=tmp_path).live_preflight(
        _mcp_preflight(
            approval_receipt_id=receipt.receipt_id,
            approval_proof_hash=receipt.proof_hash,
        ),
        lease=_mcp_lease(),
        now=_now(),
        check_credentials=True,
    )

    assert payload["decision"] == "preflight_ready"
    assert payload["credential_bindings_ready"] is True
    assert payload["credential_readiness"]["ready_binding_count"] == 1
    assert payload["credential_material_accessed"] is False


def _seed_mcp_setup(home: Path) -> None:
    setup_apply(
        home=home,
        provider_id="local-llm",
        mcp=True,
        mcp_servers=("github",),
        gateway=False,
        local=True,
    )


def _mcp_preflight(
    *,
    approval_receipt_id: str | None,
    approval_proof_hash: str | None,
) -> LivePreflightRequest:
    return LivePreflightRequest(
        preflight_id="wave79.preflight.mcp",
        approval_id="mcp-live",
        principal_id="wave79.principal.operator",
        objective_id="wave79.objective.live",
        surface_kind="mcp",
        surface_id="mcp.github",
        capability_id="mcp.echo",
        evidence_target="mneme.wave79.live_preflight",
        credential_scope="external.github.readonly",
        network_host="mcp.local",
        approval_receipt_id=approval_receipt_id,
        approval_proof_hash=approval_proof_hash,
        probe_healthy=True,
        source_pinned=True,
        mcp_description="GitHub MCP catalog profile",
        cleanup_required=True,
    )


def _receipt() -> ApprovalReceiptResult:
    return ApprovalReceiptRuntime().record(
        approval_id="mcp-live",
        principal_id="wave79.principal.operator",
        objective_id="wave79.objective.live",
        capability_id="mcp.echo",
        now=_now(),
    )


def _mcp_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave79.lease.live",
        objective_id="wave79.objective.live",
        principal_id="wave79.principal.operator",
        run_id="wave79.run.live",
        allowed_capabilities=("mcp.echo",),
        credential_scopes=("external.github.readonly",),
        network_hosts=("mcp.local",),
        budget_limit=100,
        evidence_target="mneme.wave79.live_preflight",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
