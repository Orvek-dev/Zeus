from __future__ import annotations

import pytest

from zeus_agent.acs_compat_runtime import capability_map, load_acs_manifest


def test_loads_json_manifest_with_canonical_fields() -> None:
    manifest = load_acs_manifest(
        """
        {
          "name": "host-manifest",
          "version": "1",
          "interceptions": [
            {"point": "tool.pre_call", "capability_id": "fs.write", "description": "file edits"}
          ]
        }
        """
    )
    assert manifest.name == "host-manifest"
    assert capability_map(manifest) == {"tool.pre_call": "fs.write"}


def test_tolerates_field_name_variants() -> None:
    manifest = load_acs_manifest(
        '{"name": "x", "interception_points": [{"name": "llm.request", "maps_to": "provider.generate"}]}'
    )
    assert capability_map(manifest) == {"llm.request": "provider.generate"}


def test_skips_malformed_entries() -> None:
    manifest = load_acs_manifest(
        '{"name": "x", "interceptions": [{"point": "ok", "capability_id": "fs.read"}, {"bogus": 1}, "junk"]}'
    )
    assert len(manifest.interceptions) == 1


def test_non_mapping_manifest_raises() -> None:
    with pytest.raises(ValueError):
        load_acs_manifest("[1, 2, 3]")
