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
from zeus_agent.secret_resolver_runtime import SecretResolverPlanRuntime
from zeus_agent.setup_runtime import setup_apply


def test_secret_resolver_plan_blocks_missing_reference_binding(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)

    result = SecretResolverPlanRuntime(tmp_path).plan(
        surface_kind="gateway",
        surface_id="gateway.slack",
        credential_scope="external.gateway.readonly",
        expected_endpoint="slack://ops",
    )

    assert result.decision == "blocked"
    assert "credential_binding_not_ready" in result.blocked_reasons
    assert result.credential_material_accessed is False
    assert result.env_value_read is False
    assert result.vault_value_read is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_secret_resolver_plan_uses_reference_only_binding_without_material_access(
    tmp_path: Path,
) -> None:
    _seed_gateway_setup(tmp_path)
    _bind_and_pair_gateway(tmp_path)

    result = SecretResolverPlanRuntime(tmp_path).plan(
        surface_kind="gateway",
        surface_id="gateway.slack",
        credential_scope="external.gateway.readonly",
        expected_endpoint="slack://ops",
    )

    assert result.decision == "planned"
    assert result.resolver_plan_id is not None
    assert result.binding_source == "vault_ref"
    assert result.vault_ref == "vault://zeus/external/gateway/readonly/slack"
    assert result.target_endpoint == "slack://ops"
    assert result.endpoint_binding_valid is True
    assert result.material_access_allowed is False
    assert result.credential_material_accessed is False
    assert result.no_secret_echo is True


def test_live_dry_run_execute_plan_carries_secret_resolver_plan(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    _bind_and_pair_gateway(tmp_path)

    result = LiveDryRunRuntime(home=tmp_path).run(
        surface_id="gateway.slack",
        principal_id="wave83.principal.operator",
        objective_id="wave83.objective.live",
        now=_now(),
        check_credentials=True,
    )

    assert result.decision == "planned"
    assert result.execute_plan is not None
    assert result.execute_plan.secret_resolver_plan is not None
    assert result.execute_plan.secret_resolver_plan["decision"] == "planned"
    assert result.execute_plan.secret_resolver_plan["target_endpoint"] == "slack://ops"
    assert result.execute_plan.secret_resolver_plan["credential_material_accessed"] is False
    assert result.execute_plan.secret_resolver_ready is True
    assert result.credential_material_accessed is False


def test_cli_and_python_library_secret_resolver_plan(tmp_path: Path) -> None:
    _seed_gateway_setup(tmp_path)
    _bind_and_pair_gateway(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "credentials",
            "--resolver-plan",
            "--surface-kind",
            "gateway",
            "--surface-id",
            "gateway.slack",
            "--credential-scope",
            "external.gateway.readonly",
            "--expected-endpoint",
            "slack://ops",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "planned"
    assert payload["credential_material_accessed"] is False

    library_payload = ZeusAgent(home=tmp_path).secret_resolver_plan(
        surface_kind="gateway",
        surface_id="gateway.slack",
        credential_scope="external.gateway.readonly",
        expected_endpoint="slack://ops",
    )
    assert library_payload["decision"] == "planned"
    assert library_payload["vault_value_read"] is False


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


def _bind_and_pair_gateway(home: Path) -> None:
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


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
