from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.live_dry_run_runtime import LiveDryRunRuntime
from zeus_agent.setup_runtime import setup_apply


def test_live_dry_run_can_opt_into_credential_gate(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)

    result = LiveDryRunRuntime(home=tmp_path).run(
        surface_id="gateway.slack",
        principal_id="wave80.principal.operator",
        objective_id="wave80.objective.live",
        now=_now(),
        check_credentials=True,
    )

    assert result.decision == "blocked"
    assert "preflight:credential_binding_not_ready" in result.blocked_reasons
    assert result.preflight is not None
    assert result.preflight.credential_bindings_ready is False
    assert result.preflight.credential_readiness is not None
    assert result.preflight.credential_readiness["required_binding_count"] == 1
    assert result.network_opened is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_dry_run_credential_gate_accepts_reference_binding(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    CredentialReadinessRuntime(tmp_path).bind(
        surface_kind="gateway",
        surface_id="slack",
        credential_scope="external.gateway.readonly",
        vault_ref="vault://zeus/external/gateway/readonly/slack",
    )
    GatewayPairingRuntime(tmp_path).pair(
        adapter_id="slack",
        target="slack://ops",
        proof_ref="pairing://slack/ops",
    )

    result = LiveDryRunRuntime(home=tmp_path).run(
        surface_id="gateway.slack",
        principal_id="wave80.principal.operator",
        objective_id="wave80.objective.live",
        now=_now(),
        check_credentials=True,
    )

    assert result.decision == "planned"
    assert result.preflight is not None
    assert result.preflight.decision == "preflight_ready"
    assert result.preflight.credential_bindings_ready is True
    assert result.execute_plan is not None
    assert result.execute_plan.decision == "planned"
    assert result.live_transport_enabled is False
    assert result.credential_material_accessed is False


def test_cli_live_dry_run_check_credentials_blocks_missing_binding(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-dry-run",
            "--surface-id",
            "gateway.slack",
            "--principal-id",
            "wave80.principal.operator",
            "--objective-id",
            "wave80.objective.live",
            "--home",
            str(tmp_path),
            "--check-credentials",
            "--now",
            _now().isoformat(),
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "blocked"
    assert "preflight:credential_binding_not_ready" in payload["blocked_reasons"]
    assert payload["preflight"]["credential_bindings_ready"] is False
    assert payload["network_opened"] is False


def test_python_library_live_dry_run_check_credentials(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    CredentialReadinessRuntime(tmp_path).bind(
        surface_kind="gateway",
        surface_id="slack",
        credential_scope="external.gateway.readonly",
        vault_ref="vault://zeus/external/gateway/readonly/slack",
    )
    GatewayPairingRuntime(tmp_path).pair(
        adapter_id="slack",
        target="slack://ops",
        proof_ref="pairing://slack/ops",
    )

    payload = ZeusAgent(home=tmp_path).live_dry_run(
        surface_id="gateway.slack",
        principal_id="wave80.principal.operator",
        objective_id="wave80.objective.live",
        now=_now(),
        check_credentials=True,
    )

    assert payload["decision"] == "planned"
    assert payload["preflight"]["credential_bindings_ready"] is True
    assert payload["execute_plan"]["decision"] == "planned"
    assert payload["credential_material_accessed"] is False


def _seed_gateway_setup(home: Path) -> None:
    setup_apply(
        home=home,
        provider_id="local-llm",
        mcp=False,
        gateway=True,
        gateway_adapter="slack",
        gateway_target="slack://ops",
        local=True,
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
