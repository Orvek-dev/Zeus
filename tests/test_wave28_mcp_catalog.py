from __future__ import annotations

import json

from zeus_agent.mcp_runtime import (
    curated_mcp_catalog_payload,
    default_mcp_catalog_entries,
    mcp_catalog_server_specs,
)


def test_curated_mcp_catalog_exposes_25_pinned_entries_with_10_beta_specs() -> None:
    # Given: Zeus absorbs Hermes-style MCP breadth as a curated catalog.
    entries = default_mcp_catalog_entries()
    payload = curated_mcp_catalog_payload()

    # When: beta server specs are compiled for local inspection.
    specs = mcp_catalog_server_specs()

    # Then: catalog breadth is visible, but production live execution is not claimed.
    assert len(entries) == 25
    assert payload["catalog_entry_count"] == 25
    assert payload["beta_enabled_count"] == 10
    assert len(specs) == 10
    assert all(entry.source_pinned for entry in entries)
    assert all(not spec.resources_enabled and not spec.prompts_enabled for spec in specs)
    assert payload["live_production_claimed"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["network_opened"] is False


def test_mcp_catalog_blocks_unpinned_or_injection_marked_entries() -> None:
    # Given: curated catalog output is serialized for model/UI inspection.
    payload = curated_mcp_catalog_payload()
    serialized = json.dumps(payload, sort_keys=True)

    # Then: unsafe markers never become beta-enabled visible server specs.
    assert payload["unsafe_catalog_entry_count"] == 0
    assert "ignore previous" not in serialized.lower()
    assert "sk-" not in serialized
    assert all(item["state"] in {"dry_run", "planned_wave"} for item in payload["entries"])
