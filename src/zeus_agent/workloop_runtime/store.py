from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from zeus_agent.state.idempotency import insert_or_confirm_same

from .plan import WorkLoopPlan

_PLAN_COLUMNS: Final = ("work_loop_id", "idempotency_key", "plan_json")
_STEP_COLUMNS: Final = ("work_loop_id", "lane_id", "evidence_target")
_COMPLETION_COLUMNS: Final = ("work_loop_id", "lane_id", "evidence_target")


@dataclass(frozen=True)
class WorkLoopStoreCounts:
    work_loops: int
    lane_steps: int
    completed_steps: int


@dataclass(frozen=True)
class WorkLoopNotFoundError(RuntimeError):
    work_loop_id: str

    def __str__(self) -> str:
        return "work loop not found: {0}".format(self.work_loop_id)


class SQLiteWorkLoopStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._initialize()

    def save_plan(self, plan: WorkLoopPlan, idempotency_key: str) -> WorkLoopPlan:
        key = _require_non_empty(idempotency_key, "idempotency_key")
        plan_json = _serialize_plan(plan)
        with self._connect() as connection:
            insert_or_confirm_same(
                connection,
                "INSERT INTO work_loop_plans "
                "(work_loop_id, idempotency_key, plan_json) VALUES (?, ?, ?)",
                (plan.work_loop_id, key, plan_json),
                table_name="work_loop_plans",
                columns=_PLAN_COLUMNS,
                key_columns=(
                    ("work_loop_id", plan.work_loop_id),
                    ("idempotency_key", key),
                ),
            )
            for lane in plan.lanes:
                insert_or_confirm_same(
                    connection,
                    "INSERT INTO work_loop_steps "
                    "(work_loop_id, lane_id, evidence_target) VALUES (?, ?, ?)",
                    (plan.work_loop_id, lane.lane_id, lane.evidence_target),
                    table_name="work_loop_steps",
                    columns=_STEP_COLUMNS,
                    key_columns=(
                        ("work_loop_id", plan.work_loop_id),
                        ("lane_id", lane.lane_id),
                    ),
                )
        return plan

    def complete_step(
        self,
        work_loop_id: str,
        lane_id: str,
        evidence_target: str,
    ) -> None:
        resolved_work_loop_id = _require_non_empty(work_loop_id, "work_loop_id")
        resolved_lane_id = _require_non_empty(lane_id, "lane_id")
        resolved_evidence_target = _require_non_empty(
            evidence_target,
            "evidence_target",
        )
        with self._connect() as connection:
            insert_or_confirm_same(
                connection,
                "INSERT INTO work_loop_step_completions "
                "(work_loop_id, lane_id, evidence_target) VALUES (?, ?, ?)",
                (
                    resolved_work_loop_id,
                    resolved_lane_id,
                    resolved_evidence_target,
                ),
                table_name="work_loop_step_completions",
                columns=_COMPLETION_COLUMNS,
                key_columns=(
                    ("work_loop_id", resolved_work_loop_id),
                    ("lane_id", resolved_lane_id),
                ),
            )

    def load_plan(self, work_loop_id: str) -> WorkLoopPlan:
        resolved_work_loop_id = _require_non_empty(work_loop_id, "work_loop_id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT plan_json FROM work_loop_plans WHERE work_loop_id = ?",
                (resolved_work_loop_id,),
            ).fetchone()
        if row is None:
            raise WorkLoopNotFoundError(resolved_work_loop_id)
        return WorkLoopPlan.model_validate_json(row[0])

    def counts(self) -> WorkLoopStoreCounts:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM work_loop_plans), "
                "(SELECT COUNT(*) FROM work_loop_steps), "
                "(SELECT COUNT(*) FROM work_loop_step_completions)"
            ).fetchone()
        return WorkLoopStoreCounts(
            work_loops=row[0],
            lane_steps=row[1],
            completed_steps=row[2],
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                "CREATE TABLE IF NOT EXISTS work_loop_plans ("
                "work_loop_id TEXT PRIMARY KEY,"
                "idempotency_key TEXT NOT NULL UNIQUE,"
                "plan_json TEXT NOT NULL"
                ");"
                "CREATE TABLE IF NOT EXISTS work_loop_steps ("
                "work_loop_id TEXT NOT NULL,"
                "lane_id TEXT NOT NULL,"
                "evidence_target TEXT,"
                "PRIMARY KEY (work_loop_id, lane_id),"
                "FOREIGN KEY (work_loop_id) "
                "REFERENCES work_loop_plans (work_loop_id) "
                "ON DELETE CASCADE"
                ");"
                "CREATE TABLE IF NOT EXISTS work_loop_step_completions ("
                "work_loop_id TEXT NOT NULL,"
                "lane_id TEXT NOT NULL,"
                "evidence_target TEXT NOT NULL,"
                "PRIMARY KEY (work_loop_id, lane_id),"
                "FOREIGN KEY (work_loop_id, lane_id) "
                "REFERENCES work_loop_steps (work_loop_id, lane_id) "
                "ON DELETE CASCADE"
                ");"
            )

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _serialize_plan(plan: WorkLoopPlan) -> str:
    return json.dumps(
        plan.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    )


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text
