from __future__ import annotations

from pathlib import Path

from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.mcp_runtime import default_mcp_catalog_entries
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime
from zeus_agent.setup_runtime import setup_apply


def test_mcp_catalog_exposes_credential_metadata_for_external_servers() -> None:
    github = _catalog_entry("mcp.github")
    filesystem = _catalog_entry("mcp.filesystem")

    assert github.requires_credential is True
    assert github.credential_scope == "external.github.readonly"
    assert github.source_pinned is True
    assert github.resources_enabled is False
    assert github.prompts_enabled is False
    assert filesystem.requires_credential is False
    assert filesystem.credential_scope is None


def test_mcp_settings_preserves_credential_metadata_in_local_config(tmp_path: Path) -> None:
    result = McpSettingsRuntime(tmp_path).add(server_ref="github")

    assert result.decision == "configured"
    assert result.selected_server is not None
    assert result.selected_server["server_id"] == "mcp.github"
    assert result.selected_server["requires_credential"] is True
    assert result.selected_server["credential_scope"] == "external.github.readonly"
    assert result.selected_server["resources_enabled"] is False
    assert result.selected_server["prompts_enabled"] is False
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_credential_readiness_includes_mcp_required_binding(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)

    result = CredentialReadinessRuntime(tmp_path).build()
    payload = result.to_payload()
    mcp = _binding(payload, "mcp", "mcp.github")

    assert result.required_binding_count == 3
    assert result.ready_binding_count == 0
    assert result.ready_for_live_transport is False
    assert result.mcp_binding_status == "configured_requires_credentials"
    assert mcp["credential_scope"] == "external.github.readonly"
    assert mcp["source_pinned"] is True
    assert mcp["include_tools"] == ["repo.search", "issues.list", "pulls.list"]
    assert mcp["resources_enabled"] is False
    assert mcp["prompts_enabled"] is False
    assert mcp["server_started"] is False
    assert mcp["credential_material_accessed"] is False
    assert mcp["network_opened"] is False


def test_mcp_credential_binding_can_be_registered_by_reference(tmp_path: Path) -> None:
    _seed_external_setup(tmp_path)
    runtime = CredentialReadinessRuntime(tmp_path)

    binding = runtime.bind(
        surface_kind="mcp",
        surface_id="mcp.github",
        credential_scope="external.github.readonly",
        env_ref="ZEUS_CREDENTIAL_EXTERNAL_GITHUB_READONLY",
    )
    readiness = runtime.build()
    mcp = _binding(readiness.to_payload(), "mcp", "mcp.github")

    assert binding.decision == "bound"
    assert readiness.required_binding_count == 3
    assert readiness.ready_binding_count == 1
    assert readiness.ready_for_live_transport is False
    assert mcp["binding_configured"] is True
    assert mcp["binding_source"] == "env_ref"
    assert mcp["env_value_read"] is False
    assert readiness.credential_material_accessed is False
    assert readiness.live_production_claimed is False


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


def _catalog_entry(server_id: str):
    for entry in default_mcp_catalog_entries():
        if entry.server_id == server_id:
            return entry
    raise AssertionError(f"missing catalog entry {server_id}")


def _binding(payload: dict[str, object], surface_kind: str, surface_id: str) -> dict[str, object]:
    for item in payload["credential_bindings"]:
        if not isinstance(item, dict):
            continue
        if item["surface_kind"] == surface_kind and item["surface_id"] == surface_id:
            return item
    raise AssertionError(f"missing {surface_kind}:{surface_id}")
