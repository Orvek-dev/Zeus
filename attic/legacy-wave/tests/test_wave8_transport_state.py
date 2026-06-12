from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from zeus_agent.state import IdempotencyConflictError, SQLiteTransportRuntimeStateStore
from zeus_agent.wave8_scenarios import wave8_transport_state_payload


def test_wave8_persists_transport_manifests_probes_and_evidence_links(
    tmp_path: Path,
) -> None:
    # Given: a Wave8 transport state scenario home.
    # When: provider/MCP/API/plugin manifests and probe receipts are persisted.
    payload = wave8_transport_state_payload(tmp_path)

    # Then: transport registry state is durable, linked, dry-run, and secret-safe.
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["no_secret_echo"] is True
    assert payload["live_transport"] is False
    assert payload["transport_manifest_count"] == 4
    assert payload["transport_probe_count"] == 4
    assert payload["evidence_link_count"] == 8
    assert payload["idempotency_replay_stable"] is True
    assert set(payload["transport_ids"]) == {
        "provider.external.openai",
        "mcp.local.echo",
        "api.partner.fetch",
        "plugin.pack.sync",
    }
    assert payload["health"]["api.partner.fetch"] == "unhealthy"
    assert payload["health"]["provider.external.openai"] == "healthy"

    state_db = Path(str(payload["state_db"]))
    with sqlite3.connect(state_db) as connection:
        manifest_rows = connection.execute(
            "SELECT transport_id, kind, live_transport FROM runtime_state_transport_manifests"
        ).fetchall()
        probe_rows = connection.execute(
            "SELECT probe_id, transport_id, health, network_opened "
            "FROM runtime_state_transport_probe_receipts"
        ).fetchall()

    assert len(manifest_rows) == 4
    assert len(probe_rows) == 4
    assert all(row[2] == 0 for row in manifest_rows)
    assert all(row[3] == 0 for row in probe_rows)
    assert "ghp_TEST_FIXTURE" not in json.dumps(payload, sort_keys=True)
    assert "OPENAI_API_KEY" not in json.dumps(payload, sort_keys=True)


def test_wave8_transport_state_replay_is_idempotent(tmp_path: Path) -> None:
    # Given: the same Wave8 transport state scenario is replayed into one home.
    first = wave8_transport_state_payload(tmp_path)

    # When: the same manifest/probe/evidence ids and idempotency keys are replayed.
    second = wave8_transport_state_payload(tmp_path)

    # Then: counts remain stable and duplicate transport rows are not created.
    assert first["transport_counts"] == second["transport_counts"]
    assert second["transport_manifest_count"] == 4
    assert second["transport_probe_count"] == 4
    assert second["evidence_link_count"] == 8
    assert second["idempotency_replay_stable"] is True


def test_wave8_transport_state_rejects_conflicting_manifest_replay(
    tmp_path: Path,
) -> None:
    # Given: a Wave8 manifest row already exists.
    payload = wave8_transport_state_payload(tmp_path)
    store = SQLiteTransportRuntimeStateStore(Path(str(payload["state_db"])))
    manifest = dict(payload["manifests"][0])
    manifest["display_name"] = "Conflicting Provider"

    # When: the same idempotency key is replayed with conflicting manifest content.
    with pytest.raises(IdempotencyConflictError):
        store.add_transport_manifest(
            manifest_id="transport-manifest-provider.external.openai-conflict",
            manifest=manifest,
            evidence_id="evidence-wave8-manifest-provider.external.openai",
            idempotency_key="idem-wave8-manifest-provider.external.openai",
        )

    # Then: the original manifest row remains the only persisted provider record.
    assert store.transport_counts().transport_manifests == 4
