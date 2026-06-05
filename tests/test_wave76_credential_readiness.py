from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.security_cockpit_runtime import SecurityCockpitRuntime
from zeus_agent.setup_runtime import setup_apply


def test_credential_readiness_reports_required_bindings_without_secret_access(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)

    result = CredentialReadinessRuntime(tmp_path).build()
    payload = result.to_payload()
    provider = _binding(payload, "provider", "openrouter")
    gateway = _binding(payload, "gateway", "slack")

    assert result.decision == "report"
    assert result.required_binding_count == 3
    assert result.ready_binding_count == 0
    assert result.ready_for_live_transport is False
    assert provider["credential_scope"] == "external.openrouter.readonly"
    assert provider["binding_required"] is True
    assert provider["binding_configured"] is False
    assert provider["env_value_read"] is False
    assert provider["vault_value_read"] is False
    assert gateway["credential_scope"] == "external.gateway.readonly"
    assert gateway["pairing_required"] is True
    assert gateway["pairing_configured"] is False
    assert gateway["target_allowlisted"] is True
    assert payload["mcp_configured_server_count"] == 1
    assert payload["mcp_binding_status"] == "configured_requires_credentials"
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.external_delivery_opened is False
    assert result.no_secret_echo is True
    assert result.live_production_claimed is False


def test_credential_readiness_local_provider_has_no_external_binding(tmp_path: Path) -> None:
    setup_apply(home=tmp_path, provider_id="local-llm", local=True)

    result = CredentialReadinessRuntime(tmp_path).build()

    assert result.decision == "report"
    assert result.required_binding_count == 0
    assert result.ready_binding_count == 0
    assert result.ready_for_live_transport is True
    assert result.mcp_configured_server_count == 0
    assert result.gateway_configured_target_count == 0
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_cli_credentials_reports_readiness_with_home(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(app, ["credentials", "--home", str(tmp_path), "--json"])

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "report"
    assert payload["required_binding_count"] == 3
    assert payload["credential_bindings"][0]["credential_material_accessed"] is False
    assert payload["ready_for_live_transport"] is False
    assert payload["live_production_claimed"] is False


def test_security_cockpit_can_include_credential_readiness(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)

    result = SecurityCockpitRuntime(home=tmp_path).build(include_credentials=True)

    assert result.decision == "report"
    assert result.credential_readiness is not None
    assert result.credential_readiness["required_binding_count"] == 3
    assert result.credential_readiness["credential_material_accessed"] is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_security_cli_can_include_credential_readiness(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(
        app,
        ["security", "--include-credentials", "--home", str(tmp_path), "--json"],
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["credential_readiness"]["required_binding_count"] == 3
    assert payload["credential_readiness"]["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_live_cockpit_configuration_context_includes_credential_readiness(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    runner = CliRunner()

    completed = runner.invoke(app, ["live", "--home", str(tmp_path), "--json"])

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    readiness = payload["configuration_context"]["credential_readiness"]
    assert readiness["required_binding_count"] == 3
    assert readiness["ready_for_live_transport"] is False
    assert readiness["credential_material_accessed"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_credential_readiness(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    agent = ZeusAgent(home=tmp_path)

    credentials = agent.credential_readiness()
    security = agent.security_status(include_credentials=True)
    live = agent.live_status()

    assert credentials["required_binding_count"] == 3
    assert security["credential_readiness"]["required_binding_count"] == 3
    assert live["configuration_context"]["credential_readiness"]["required_binding_count"] == 3
    assert credentials["credential_material_accessed"] is False
    assert security["credential_material_accessed"] is False
    assert live["live_production_claimed"] is False


def test_credential_readiness_does_not_echo_secret_like_config_values(tmp_path: Path) -> None:
    raw_secret = "sk-" + "wave76-secret"
    (tmp_path / "gateway-config.json").write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "adapter_id": "slack",
                        "display_name": "Slack",
                        "target": "slack://" + raw_secret,
                        "auth_required": True,
                        "pairing_required": True,
                        "target_allowlisted": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = CredentialReadinessRuntime(tmp_path).build()
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True
    assert result.credential_material_accessed is False


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
