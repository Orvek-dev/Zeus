from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from zeus_agent.kernel.evidence import MnemeEvidenceRecord
from zeus_agent.state.idempotency import SQLiteValue, insert_or_confirm_same
from zeus_agent.state.runtime_schema import RUNTIME_SCHEMA
from zeus_agent.state.sqlite_store import SQLiteStateStore


class RuntimeExecutionCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_executions: int
    connector_executions: int
    execution_evidence_links: int
    promotion_attempts: int


class SQLiteRuntimeStateStore:
    def __init__(self, db_path: Path) -> None:
        self._base = SQLiteStateStore(db_path)
        self.db_path = self._base.db_path
        with self._connect() as connection:
            for statement in RUNTIME_SCHEMA:
                connection.execute(statement)

    def add_evidence(self, evidence_id: str, record: MnemeEvidenceRecord) -> None:
        self._base.add_evidence(evidence_id, record)

    def add_provider_execution(
        self,
        *,
        provider_execution_id: str,
        run_id: str,
        goal_contract_id: str,
        provider: str,
        provider_id: str,
        model_id: str,
        envelope: dict[str, object],
        broker_decision: str,
        evidence_id: str,
        idempotency_key: str,
        live_transport: bool,
    ) -> None:
        columns = (
            "provider_execution_id",
            "run_id",
            "goal_contract_id",
            "provider",
            "provider_id",
            "model_id",
            "envelope_json",
            "broker_decision",
            "evidence_id",
            "idempotency_key",
            "live_transport",
        )
        values: tuple[SQLiteValue, ...] = (
            provider_execution_id,
            run_id,
            goal_contract_id,
            provider,
            provider_id,
            model_id,
            json.dumps(envelope, sort_keys=True),
            broker_decision,
            evidence_id,
            idempotency_key,
            int(live_transport),
        )
        self._insert_or_confirm_same(
            "INSERT INTO runtime_state_provider_executions("
            "provider_execution_id, run_id, goal_contract_id, provider, provider_id, "
            "model_id, envelope_json, broker_decision, evidence_id, idempotency_key, "
            "live_transport) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
            table_name="runtime_state_provider_executions",
            columns=columns,
            key_columns=(
                ("provider_execution_id", provider_execution_id),
                ("idempotency_key", idempotency_key),
            ),
        )

    def add_connector_execution(
        self,
        *,
        connector_execution_id: str,
        run_id: str,
        goal_contract_id: str,
        connector_id: str,
        connector_kind: str,
        capability_id: str,
        envelope: dict[str, object],
        broker_decision: str,
        handler_executed: bool,
        evidence_id: str,
        idempotency_key: str,
        live_transport: bool,
    ) -> None:
        columns = (
            "connector_execution_id",
            "run_id",
            "goal_contract_id",
            "connector_id",
            "connector_kind",
            "capability_id",
            "envelope_json",
            "broker_decision",
            "handler_executed",
            "evidence_id",
            "idempotency_key",
            "live_transport",
        )
        values: tuple[SQLiteValue, ...] = (
            connector_execution_id,
            run_id,
            goal_contract_id,
            connector_id,
            connector_kind,
            capability_id,
            json.dumps(envelope, sort_keys=True),
            broker_decision,
            int(handler_executed),
            evidence_id,
            idempotency_key,
            int(live_transport),
        )
        self._insert_or_confirm_same(
            "INSERT INTO runtime_state_connector_executions("
            "connector_execution_id, run_id, goal_contract_id, connector_id, "
            "connector_kind, capability_id, envelope_json, broker_decision, "
            "handler_executed, evidence_id, idempotency_key, live_transport"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
            table_name="runtime_state_connector_executions",
            columns=columns,
            key_columns=(
                ("connector_execution_id", connector_execution_id),
                ("idempotency_key", idempotency_key),
            ),
        )

    def add_execution_evidence_link(
        self,
        *,
        execution_kind: str,
        execution_id: str,
        evidence_id: str,
    ) -> None:
        self._execute(
            "INSERT OR IGNORE INTO runtime_state_execution_evidence_links("
            "execution_kind, execution_id, evidence_id"
            ") VALUES (?, ?, ?)",
            (execution_kind, execution_id, evidence_id),
        )

    def add_transport_promotion(
        self,
        *,
        promotion_id: str,
        capability_id: str,
        transport_kind: str,
        decision: str,
        reason: str,
        approval_required: bool,
        handler_executed: bool,
        network_opened: bool,
        retry_policy: dict[str, int],
        rollback_plan: dict[str, object],
        idempotency_key: str,
    ) -> None:
        columns = (
            "promotion_id",
            "capability_id",
            "transport_kind",
            "decision",
            "reason",
            "approval_required",
            "handler_executed",
            "network_opened",
            "retry_policy_json",
            "rollback_plan_json",
            "idempotency_key",
        )
        values: tuple[SQLiteValue, ...] = (
            promotion_id,
            capability_id,
            transport_kind,
            decision,
            reason,
            int(approval_required),
            int(handler_executed),
            int(network_opened),
            json.dumps(retry_policy, sort_keys=True),
            json.dumps(rollback_plan, sort_keys=True),
            idempotency_key,
        )
        self._insert_or_confirm_same(
            "INSERT INTO runtime_state_transport_promotions("
            "promotion_id, capability_id, transport_kind, decision, reason, "
            "approval_required, handler_executed, network_opened, retry_policy_json, "
            "rollback_plan_json, idempotency_key"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
            table_name="runtime_state_transport_promotions",
            columns=columns,
            key_columns=(("promotion_id", promotion_id), ("idempotency_key", idempotency_key)),
        )

    def runtime_counts(self) -> RuntimeExecutionCounts:
        return RuntimeExecutionCounts(
            provider_executions=self._count("runtime_state_provider_executions"),
            connector_executions=self._count("runtime_state_connector_executions"),
            execution_evidence_links=self._count("runtime_state_execution_evidence_links"),
            promotion_attempts=self._count("runtime_state_transport_promotions"),
        )

    def _execute(self, statement: str, values: tuple[object, ...]) -> None:
        with self._connect() as connection:
            connection.execute(statement, values)

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
