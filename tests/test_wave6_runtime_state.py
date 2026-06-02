from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord
from zeus_agent.state import IdempotencyConflictError, SQLiteRuntimeStateStore
from zeus_agent.wave6_scenarios import wave6_runtime_state_payload


def test_wave6_persists_provider_and_connector_execution_envelopes(
    tmp_path: Path,
) -> None:
    # Given: a Wave6 scenario home with no external transports.
    # When: provider and connector dry-run executions are persisted.
    payload = wave6_runtime_state_payload(tmp_path)

    # Then: runtime execution state links envelopes, evidence, and idempotency keys.
    assert payload["fake_local_only"] is True
    assert payload["no_external_side_effects"] is True
    assert payload["no_secret_echo"] is True
    assert payload["live_transport"] is False
    assert payload["runtime_counts"] == {
        "provider_executions": 1,
        "connector_executions": 1,
        "execution_evidence_links": 2,
        "promotion_attempts": 0,
    }
    assert payload["provider_execution"]["idempotency_key"] == "idem-wave6-provider-001"
    assert payload["connector_execution"]["idempotency_key"] == "idem-wave6-connector-001"
    assert payload["provider_execution"]["envelope"]["transport"] == "dry_run"
    assert payload["connector_execution"]["envelope"]["transport"] == "dry_run"

    state_db = Path(str(payload["state_db"]))
    with sqlite3.connect(state_db) as connection:
        provider_rows = connection.execute(
            """
            SELECT provider_execution_id, provider_id, model_id, idempotency_key, live_transport
            FROM runtime_state_provider_executions
            """
        ).fetchall()
        connector_rows = connection.execute(
            """
            SELECT connector_execution_id, connector_id, capability_id, idempotency_key, handler_executed
            FROM runtime_state_connector_executions
            """
        ).fetchall()
        link_rows = connection.execute(
            """
            SELECT execution_kind, execution_id, evidence_id
            FROM runtime_state_execution_evidence_links
            ORDER BY execution_kind
            """
        ).fetchall()
        connector_evidence_rows = connection.execute(
            """
            SELECT criterion_id
            FROM evidence_state_records
            WHERE evidence_id = 'evidence-wave6-connector-001'
            """
        ).fetchall()

    assert provider_rows == [
        (
            "provider-exec-wave6-001",
            "local-private",
            "local-private-stub",
            "idem-wave6-provider-001",
            0,
        )
    ]
    assert connector_rows == [
        (
            "connector-exec-wave6-001",
            "mcp-conn",
            "mcp.echo",
            "idem-wave6-connector-001",
            1,
        )
    ]
    assert link_rows == [
        ("connector", "connector-exec-wave6-001", "evidence-wave6-connector-001"),
        ("provider", "provider-exec-wave6-001", "evidence-wave6-provider-001"),
    ]
    assert connector_evidence_rows == [("REQ-ZEUS-WAVE6-002:S1",)]


def test_wave6_runtime_state_is_idempotent_by_execution_key(tmp_path: Path) -> None:
    # Given: the same Wave6 state scenario is replayed into the same home.
    first = wave6_runtime_state_payload(tmp_path)

    # When: it is replayed with the same execution ids and idempotency keys.
    second = wave6_runtime_state_payload(tmp_path)

    # Then: counts remain stable and no duplicate runtime rows are created.
    assert first["runtime_counts"] == second["runtime_counts"]
    assert second["runtime_counts"]["provider_executions"] == 1
    assert second["runtime_counts"]["connector_executions"] == 1

    serialized = json.dumps(second, sort_keys=True)
    assert "ghp_TEST_FIXTURE" not in serialized
    assert "OPENAI_API_KEY" not in serialized


def test_wave6_runtime_state_rejects_conflicting_provider_replay(tmp_path: Path) -> None:
    # Given: a Wave6 provider execution has already been persisted.
    payload = wave6_runtime_state_payload(tmp_path)
    store = SQLiteRuntimeStateStore(Path(str(payload["state_db"])))

    # When: the same idempotency key is replayed with different execution state.
    with pytest.raises(IdempotencyConflictError):
        store.add_provider_execution(
            provider_execution_id="provider-exec-wave6-conflict",
            run_id="wave6-run",
            goal_contract_id="wave6-goal",
            provider="local",
            provider_id="local-private",
            model_id="local-private-stub",
            envelope=dict(payload["provider_execution"]["envelope"]),
            broker_decision="selected",
            evidence_id="evidence-wave6-provider-001",
            idempotency_key="idem-wave6-provider-001",
            live_transport=True,
        )

    # Then: the original dry-run row remains the only provider execution.
    assert store.runtime_counts().provider_executions == 1


def test_wave6_evidence_state_rejects_conflicting_replay(tmp_path: Path) -> None:
    # Given: a runtime store with one provider evidence record.
    payload = wave6_runtime_state_payload(tmp_path)
    store = SQLiteRuntimeStateStore(Path(str(payload["state_db"])))

    # When: the same evidence id is replayed with conflicting status and criterion.
    with pytest.raises(IdempotencyConflictError):
        store.add_evidence(
            "evidence-wave6-provider-001",
            MnemeEvidenceRecord(
                run_id="wave6-run",
                goal_contract_id="wave6-goal",
                criterion_id="REQ-ZEUS-WAVE6-999:S1",
                evidence_type="provider_execution",
                summary="conflicting provider evidence",
                status=EvidenceStatus.FAIL,
                capability_id="provider.local.generate",
            ),
        )

    # Then: the conflict is rejected instead of silently masking stale evidence.
    assert store.runtime_counts().provider_executions == 1


def test_wave6_runtime_state_rejects_conflicting_connector_replay(tmp_path: Path) -> None:
    # Given: a Wave6 connector execution has already been persisted.
    payload = wave6_runtime_state_payload(tmp_path)
    store = SQLiteRuntimeStateStore(Path(str(payload["state_db"])))

    # When: the same connector idempotency key is replayed with different state.
    with pytest.raises(IdempotencyConflictError):
        store.add_connector_execution(
            connector_execution_id="connector-exec-wave6-conflict",
            run_id="wave6-run",
            goal_contract_id="wave6-goal",
            connector_id="mcp-conn",
            connector_kind="mcp",
            capability_id="mcp.echo",
            envelope=dict(payload["connector_execution"]["envelope"]),
            broker_decision="blocked",
            handler_executed=False,
            evidence_id="evidence-wave6-connector-001",
            idempotency_key="idem-wave6-connector-001",
            live_transport=False,
        )

    # Then: the original connector row remains the only connector execution.
    assert store.runtime_counts().connector_executions == 1


def test_wave6_runtime_state_rejects_conflicting_promotion_replay(tmp_path: Path) -> None:
    # Given: a Wave6 promotion attempt has already been persisted.
    store = SQLiteRuntimeStateStore(tmp_path / "wave6-promotion.sqlite3")
    retry_policy = {"max_attempts": 3, "backoff_seconds": 5}
    rollback_plan = {
        "command": "disable-live-transport",
        "target": "provider.external.generate",
        "executed": False,
    }
    store.add_transport_promotion(
        promotion_id="promotion-wave6-001",
        capability_id="provider.external.generate",
        transport_kind="provider",
        decision="blocked",
        reason="live_transport_not_authorized",
        approval_required=True,
        handler_executed=False,
        network_opened=False,
        retry_policy=retry_policy,
        rollback_plan=rollback_plan,
        idempotency_key="idem-wave6-promotion-001",
    )

    # When: the same promotion idempotency key is replayed with an allowed state.
    with pytest.raises(IdempotencyConflictError):
        store.add_transport_promotion(
            promotion_id="promotion-wave6-conflict",
            capability_id="provider.external.generate",
            transport_kind="provider",
            decision="allowed",
            reason="live_transport_authorized",
            approval_required=False,
            handler_executed=True,
            network_opened=True,
            retry_policy=retry_policy,
            rollback_plan=rollback_plan,
            idempotency_key="idem-wave6-promotion-001",
        )

    # Then: the original blocked promotion remains the only promotion attempt.
    assert store.runtime_counts().promotion_attempts == 1
