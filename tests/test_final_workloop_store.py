from __future__ import annotations

from pathlib import Path

import pytest

from final_workloop_fixtures import objective_contract, passed_obligations, valid_lanes


def test_work_loop_plan_persists_and_resumes_without_duplicate_steps(tmp_path: Path) -> None:
    from zeus_agent.workloop_runtime import SQLiteWorkLoopStore, WorkLoopBuilder

    plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=passed_obligations(),
        work_loop_id="workloop-final-persistent",
    )
    db_path = tmp_path / "workloop.sqlite"
    store = SQLiteWorkLoopStore(db_path)

    store.save_plan(plan, idempotency_key="save-final-workloop")
    store.complete_step(
        plan.work_loop_id,
        "workloop-runtime",
        "tests/test_final_workloop_store.py::test_work_loop_plan_persists_and_resumes_without_duplicate_steps",
    )
    counts_after_run = store.counts()

    resumed_store = SQLiteWorkLoopStore(db_path)
    resumed_store.save_plan(plan, idempotency_key="save-final-workloop")
    resumed_store.complete_step(
        plan.work_loop_id,
        "workloop-runtime",
        "tests/test_final_workloop_store.py::test_work_loop_plan_persists_and_resumes_without_duplicate_steps",
    )
    loaded_plan = resumed_store.load_plan(plan.work_loop_id)
    counts_after_resume = resumed_store.counts()

    assert loaded_plan == plan
    assert counts_after_run.work_loops == 1
    assert counts_after_run.lane_steps == len(plan.lanes)
    assert counts_after_run.completed_steps == 1
    assert counts_after_resume == counts_after_run


def test_conflicting_idempotent_work_loop_replay_fails_closed(tmp_path: Path) -> None:
    from zeus_agent.state.idempotency import IdempotencyConflictError
    from zeus_agent.workloop_runtime import SQLiteWorkLoopStore, WorkLoopBuilder

    store = SQLiteWorkLoopStore(tmp_path / "workloop.sqlite")
    original_plan = WorkLoopBuilder().build(
        contract=objective_contract(),
        lanes=valid_lanes(),
        verification_obligations=passed_obligations(),
        work_loop_id="workloop-final-persistent",
    )
    conflicting_plan = WorkLoopBuilder().build(
        goal_contract_id="goal-final-workloop",
        normalized_goal="changed replay payload",
        deliverables=["work loop plan", "verification summary"],
        acceptance_criteria=["REQ-ZEUS-FINAL-002:S1", "REQ-ZEUS-FINAL-003:S1"],
        lanes=valid_lanes(),
        verification_obligations=passed_obligations(),
        work_loop_id="workloop-final-persistent",
    )
    store.save_plan(original_plan, idempotency_key="save-final-workloop")

    with pytest.raises(IdempotencyConflictError):
        store.save_plan(conflicting_plan, idempotency_key="save-final-workloop")

    assert store.load_plan(original_plan.work_loop_id) == original_plan
    assert store.counts().work_loops == 1
