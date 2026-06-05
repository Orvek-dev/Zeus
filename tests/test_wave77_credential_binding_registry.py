from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.setup_runtime import setup_apply


def test_credential_binding_registry_marks_required_bindings_ready_without_secret_values(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    runtime = CredentialReadinessRuntime(tmp_path)

    provider = runtime.bind(
        surface_kind="provider",
        surface_id="openrouter",
        credential_scope="external.openrouter.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_OPENROUTER_READONLY",
    )
    gateway = runtime.bind(
        surface_kind="gateway",
        surface_id="slack",
        credential_scope="external.gateway.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_GATEWAY_READONLY_SLACK",
    )
    mcp = runtime.bind(
        surface_kind="mcp",
        surface_id="mcp.github",
        credential_scope="external.github.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_GITHUB_READONLY",
    )
    readiness = runtime.build()
    provider_binding = _binding(readiness.to_payload(), "provider", "openrouter")
    mcp_binding = _binding(readiness.to_payload(), "mcp", "mcp.github")
    gateway_binding = _binding(readiness.to_payload(), "gateway", "slack")

    assert provider.decision == "bound"
    assert gateway.decision == "bound"
    assert mcp.decision == "bound"
    assert readiness.required_binding_count == 3
    assert readiness.ready_binding_count == 3
    assert readiness.ready_for_live_transport is True
    assert readiness.binding_registry_available is True
    assert provider_binding["binding_configured"] is True
    assert provider_binding["binding_source"] == "env_ref"
    assert provider_binding["env_value_read"] is False
    assert gateway_binding["binding_configured"] is True
    assert gateway_binding["binding_source"] == "env_ref"
    assert gateway_binding["credential_material_accessed"] is False
    assert mcp_binding["binding_configured"] is True
    assert mcp_binding["binding_source"] == "env_ref"
    assert mcp_binding["env_value_read"] is False
    assert readiness.credential_material_accessed is False
    assert readiness.network_opened is False
    assert readiness.live_production_claimed is False


def test_cli_credentials_bind_writes_reference_only_binding(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    runner = CliRunner()

    bound = runner.invoke(
        app,
        [
            "credentials",
            "--bind",
            "--surface-kind",
            "provider",
            "--surface-id",
            "openrouter",
            "--credential-scope",
            "external.openrouter.readonly",
            "--env-ref",
            "ZEUS_CREDENTIAL_EXTERNAL_OPENROUTER_READONLY",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )
    listed = runner.invoke(app, ["credentials", "--home", str(tmp_path), "--json"])

    assert bound.exit_code == 0, bound.stdout
    bound_payload = json.loads(bound.stdout)
    listed_payload = json.loads(listed.stdout)
    assert bound_payload["decision"] == "bound"
    assert bound_payload["binding"]["env_ref"] == "ZEUS_CREDENTIAL_EXTERNAL_OPENROUTER_READONLY"
    assert bound_payload["env_value_read"] is False
    assert listed_payload["ready_binding_count"] == 1
    assert listed_payload["credential_bindings"][0]["binding_configured"] is True
    assert listed_payload["credential_material_accessed"] is False


def test_python_library_credentials_bind_and_live_status_share_registry(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    agent = ZeusAgent(home=tmp_path)

    agent.credential_bind(
        surface_kind="provider",
        surface_id="openrouter",
        credential_scope="external.openrouter.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_OPENROUTER_READONLY",
    )
    agent.credential_bind(
        surface_kind="gateway",
        surface_id="slack",
        credential_scope="external.gateway.readonly",
        vault_ref="vault://zeus/external/gateway/readonly/slack",
    )
    agent.credential_bind(
        surface_kind="mcp",
        surface_id="mcp.github",
        credential_scope="external.github.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_GITHUB_READONLY",
    )

    credentials = agent.credential_readiness()
    live = agent.live_status()

    assert credentials["ready_binding_count"] == 3
    assert credentials["ready_for_live_transport"] is True
    assert live["configuration_context"]["credential_readiness"]["ready_binding_count"] == 3
    assert live["configuration_context"]["credential_readiness"]["ready_for_live_transport"] is True
    assert credentials["vault_value_read"] is False
    assert live["live_production_claimed"] is False


def test_credential_binding_registry_blocks_secret_like_references_without_writing(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    raw_secret = "sk-" + "wave77-secret"

    result = CredentialReadinessRuntime(tmp_path).bind(
        surface_kind="provider",
        surface_id="openrouter",
        credential_scope="external.openrouter.readonly",
        env_ref=raw_secret,
    )
    readiness = CredentialReadinessRuntime(tmp_path).build()
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    assert result.decision == "blocked"
    assert result.blocked_reasons == ("unsafe_credential_reference",)
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert readiness.ready_binding_count == 0
    assert readiness.credential_material_accessed is False
    assert result.live_production_claimed is False


def _seed_external_setup(home: Path) -> None:
    setup_apply(
        home=home,
        provider_id="openrouter/qwen",
        mcp=True,
        mcp_servers=("github",),
        gateway=True,
        gateway_adapter="slack",
        gateway_target="slack://ops",
    )


def _binding(payload: dict[str, object], surface_kind: str, surface_id: str) -> dict[str, object]:
    for item in payload["credential_bindings"]:
        if not isinstance(item, dict):
            continue
        if item["surface_kind"] == surface_kind and item["surface_id"] == surface_id:
            return item
    raise AssertionError(f"missing {surface_kind}:{surface_id}")
