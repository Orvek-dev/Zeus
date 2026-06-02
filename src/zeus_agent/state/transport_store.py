from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from zeus_agent.kernel.evidence import MnemeEvidenceRecord
from zeus_agent.state.idempotency import SQLiteValue, insert_or_confirm_same
from zeus_agent.state.sqlite_store import SQLiteStateStore
from zeus_agent.state.transport_schema import TRANSPORT_RUNTIME_SCHEMA


class TransportStateCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transport_manifests: int
    transport_probe_receipts: int
    transport_health: int
    transport_policy_blocks: int
    transport_evidence_links: int


class SQLiteTransportRuntimeStateStore:
    def __init__(self, db_path: Path) -> None:
        self._base = SQLiteStateStore(db_path)
        self.db_path = self._base.db_path
        with self._connect() as connection:
            for statement in TRANSPORT_RUNTIME_SCHEMA:
                connection.execute(statement)

    def add_evidence(self, evidence_id: str, record: MnemeEvidenceRecord) -> None:
        self._base.add_evidence(evidence_id, record)

    def add_transport_manifest(
        self,
        *,
        manifest_id: str,
        manifest: dict[str, object],
        evidence_id: str,
        idempotency_key: str,
    ) -> None:
        values: tuple[SQLiteValue, ...] = (
            manifest_id,
            str(manifest["transport_id"]),
            str(manifest["kind"]),
            str(manifest["capability_id"]),
            json.dumps(manifest, sort_keys=True),
            evidence_id,
            idempotency_key,
            int(bool(manifest["live_transport"])),
        )
        self._insert_or_confirm_same(
            "INSERT INTO runtime_state_transport_manifests("
            "manifest_id, transport_id, kind, capability_id, payload_json, "
            "evidence_id, idempotency_key, live_transport"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            values,
            table_name="runtime_state_transport_manifests",
            columns=(
                "manifest_id",
                "transport_id",
                "kind",
                "capability_id",
                "payload_json",
                "evidence_id",
                "idempotency_key",
                "live_transport",
            ),
            key_columns=(("manifest_id", manifest_id), ("idempotency_key", idempotency_key)),
        )
        self.add_transport_evidence_link(
            record_kind="manifest",
            record_id=manifest_id,
            evidence_id=evidence_id,
        )

    def add_transport_probe_receipt(
        self,
        *,
        probe_receipt_id: str,
        receipt: dict[str, object],
        evidence_id: str,
        idempotency_key: str,
    ) -> None:
        values: tuple[SQLiteValue, ...] = (
            probe_receipt_id,
            str(receipt["probe_id"]),
            str(receipt["transport_id"]),
            str(receipt["health"]),
            json.dumps(receipt, sort_keys=True),
            evidence_id,
            idempotency_key,
            int(bool(receipt["handler_executed"])),
            int(bool(receipt["network_opened"])),
            int(bool(receipt["side_effects"])),
        )
        self._insert_or_confirm_same(
            "INSERT INTO runtime_state_transport_probe_receipts("
            "probe_receipt_id, probe_id, transport_id, health, payload_json, "
            "evidence_id, idempotency_key, handler_executed, network_opened, side_effects"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
            table_name="runtime_state_transport_probe_receipts",
            columns=(
                "probe_receipt_id",
                "probe_id",
                "transport_id",
                "health",
                "payload_json",
                "evidence_id",
                "idempotency_key",
                "handler_executed",
                "network_opened",
                "side_effects",
            ),
            key_columns=(
                ("probe_receipt_id", probe_receipt_id),
                ("idempotency_key", idempotency_key),
            ),
        )
        self.add_transport_evidence_link(
            record_kind="probe",
            record_id=probe_receipt_id,
            evidence_id=evidence_id,
        )

    def add_transport_health(
        self,
        *,
        transport_id: str,
        health: str,
        evidence_id: str,
        idempotency_key: str,
    ) -> None:
        self._insert_or_confirm_same(
            "INSERT INTO runtime_state_transport_health("
            "transport_id, health, evidence_id, idempotency_key"
            ") VALUES (?, ?, ?, ?)",
            (transport_id, health, evidence_id, idempotency_key),
            table_name="runtime_state_transport_health",
            columns=("transport_id", "health", "evidence_id", "idempotency_key"),
            key_columns=(("transport_id", transport_id), ("idempotency_key", idempotency_key)),
        )

    def add_transport_policy_block(
        self,
        *,
        policy_block_id: str,
        block: dict[str, object],
        evidence_id: str,
        idempotency_key: str,
    ) -> None:
        transport_id = block.get("transport_id")
        values: tuple[SQLiteValue, ...] = (
            policy_block_id,
            str(block["reason"]),
            str(transport_id) if transport_id is not None else None,
            json.dumps(block, sort_keys=True),
            evidence_id,
            idempotency_key,
            int(bool(block["handler_executed"])),
            int(bool(block["network_opened"])),
        )
        self._insert_or_confirm_same(
            "INSERT INTO runtime_state_transport_policy_blocks("
            "policy_block_id, reason, transport_id, payload_json, evidence_id, "
            "idempotency_key, handler_executed, network_opened"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            values,
            table_name="runtime_state_transport_policy_blocks",
            columns=(
                "policy_block_id",
                "reason",
                "transport_id",
                "payload_json",
                "evidence_id",
                "idempotency_key",
                "handler_executed",
                "network_opened",
            ),
            key_columns=(
                ("policy_block_id", policy_block_id),
                ("idempotency_key", idempotency_key),
            ),
        )

    def add_transport_evidence_link(
        self,
        *,
        record_kind: str,
        record_id: str,
        evidence_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO runtime_state_transport_evidence_links("
                "record_kind, record_id, evidence_id"
                ") VALUES (?, ?, ?)",
                (record_kind, record_id, evidence_id),
            )

    def transport_counts(self) -> TransportStateCounts:
        return TransportStateCounts(
            transport_manifests=self._count("runtime_state_transport_manifests"),
            transport_probe_receipts=self._count("runtime_state_transport_probe_receipts"),
            transport_health=self._count("runtime_state_transport_health"),
            transport_policy_blocks=self._count("runtime_state_transport_policy_blocks"),
            transport_evidence_links=self._count("runtime_state_transport_evidence_links"),
        )

    def _insert_or_confirm_same(
        self,
        statement: str,
        values: tuple[SQLiteValue, ...],
        *,
        table_name: str,
        columns: tuple[str, ...],
        key_columns: tuple[tuple[str, str], ...],
    ) -> None:
        with self._connect() as connection:
            insert_or_confirm_same(
                connection,
                statement,
                values,
                table_name=table_name,
                columns=columns,
                key_columns=key_columns,
            )

    def _count(self, table_name: str) -> int:
        with self._connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
