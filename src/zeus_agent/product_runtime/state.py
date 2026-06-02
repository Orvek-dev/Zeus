from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from zeus_agent.product_runtime.models import ProductRuntimeSnapshot
from zeus_agent.state.idempotency import SQLiteValue, insert_or_confirm_same


class ProductRuntimeStateCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_snapshots: int


class SQLiteProductRuntimeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS product_runtime_snapshots("
                "snapshot_id TEXT PRIMARY KEY, "
                "objective_id TEXT NOT NULL, "
                "snapshot_json TEXT NOT NULL, "
                "idempotency_key TEXT NOT NULL UNIQUE"
                ")",
            )

    def add_snapshot(
        self,
        *,
        snapshot_id: str,
        snapshot: ProductRuntimeSnapshot,
        idempotency_key: str,
    ) -> None:
        payload = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True)
        columns = ("snapshot_id", "objective_id", "snapshot_json", "idempotency_key")
        values: tuple[SQLiteValue, ...] = (
            snapshot_id,
            snapshot.objective_id,
            payload,
            idempotency_key,
        )
        with self._connect() as connection:
            insert_or_confirm_same(
                connection,
                "INSERT INTO product_runtime_snapshots("
                "snapshot_id, objective_id, snapshot_json, idempotency_key"
                ") VALUES (?, ?, ?, ?)",
                values,
                table_name="product_runtime_snapshots",
                columns=columns,
                key_columns=(("snapshot_id", snapshot_id), ("idempotency_key", idempotency_key)),
            )

    def load_snapshot(self, snapshot_id: str) -> ProductRuntimeSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM product_runtime_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        return ProductRuntimeSnapshot.model_validate(json.loads(str(row[0])))

    def counts(self) -> ProductRuntimeStateCounts:
        with self._connect() as connection:
            count = int(
                connection.execute("SELECT COUNT(*) FROM product_runtime_snapshots").fetchone()[0],
            )
        return ProductRuntimeStateCounts(product_snapshots=count)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
