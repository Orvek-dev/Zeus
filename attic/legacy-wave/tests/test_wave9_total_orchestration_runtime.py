from __future__ import annotations

from zeus_agent.orchestration_runtime import ParallelScheduler, ParallelTaskSpec


def test_parallel_scheduler_orders_disjoint_tasks_and_blocks_cycles() -> None:
    security = ParallelTaskSpec(
        task_id="security-constraints",
        owned_paths=("src/zeus_agent/security/**",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_parallel_scheduler_orders_disjoint_tasks_and_blocks_cycles",
        live_capable=False,
        security_decisions=("allow_live_network",),
        subagent_depth=1,
    )
    research = ParallelTaskSpec(
        task_id="research-notes",
        owned_paths=("assets/research",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_parallel_scheduler_orders_disjoint_tasks_and_blocks_cycles",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    compose = ParallelTaskSpec(
        task_id="compose-summary",
        owned_paths=("docs/research/summary.md",),
        depends_on=("research-notes",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_parallel_scheduler_orders_disjoint_tasks_and_blocks_cycles",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    schedule = ParallelScheduler().plan([security, research, compose])

    assert schedule.decision == "planned"
    assert schedule.dry_run is True
    assert len(schedule.waves) == 2
    assert schedule.waves[0].wave_index == 0
    assert schedule.waves[0].task_ids == ("research-notes", "security-constraints")
    assert schedule.waves[1].task_ids == ("compose-summary",)

    cycle_a = ParallelTaskSpec(
        task_id="cycle-a",
        owned_paths=("src/zeus_agent/orchestration_runtime/**",),
        depends_on=("cycle-b",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_parallel_scheduler_orders_disjoint_tasks_and_blocks_cycles",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    cycle_b = ParallelTaskSpec(
        task_id="cycle-b",
        owned_paths=("src/zeus_agent/agent_runtime/**",),
        depends_on=("cycle-a",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_parallel_scheduler_orders_disjoint_tasks_and_blocks_cycles",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    cycle_schedule = ParallelScheduler().plan([cycle_a, cycle_b])

    assert cycle_schedule.decision == "blocked"
    assert cycle_schedule.blocked_reasons == ("cycle:cycle-a<->cycle-b",)


def test_overlap_write_scopes_blocks_parallel_wave() -> None:
    task_one = ParallelTaskSpec(
        task_id="task-one",
        owned_paths=("src/zeus_agent/orchestration_runtime",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_overlap_write_scopes_blocks_parallel_wave",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    task_two = ParallelTaskSpec(
        task_id="task-two",
        owned_paths=("src/zeus_agent/orchestration_runtime/models.py",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_overlap_write_scopes_blocks_parallel_wave",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )

    schedule = ParallelScheduler().plan([task_one, task_two])

    assert schedule.decision == "blocked"
    assert "owned_path_conflict:task-one:task-two" in schedule.blocked_reasons


def test_overlap_write_scopes_allows_dependency_ordered_tasks() -> None:
    task_one = ParallelTaskSpec(
        task_id="task-one",
        owned_paths=("src/zeus_agent/orchestration_runtime",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_overlap_write_scopes_allows_dependency_ordered_tasks",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    task_two = ParallelTaskSpec(
        task_id="task-two",
        owned_paths=("src/zeus_agent/orchestration_runtime/models.py",),
        depends_on=("task-one",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_overlap_write_scopes_allows_dependency_ordered_tasks",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )

    schedule = ParallelScheduler().plan([task_one, task_two])

    assert schedule.decision == "planned"
    assert len(schedule.waves) == 2
    assert schedule.waves[0].task_ids == ("task-one",)
    assert schedule.waves[1].task_ids == ("task-two",)


def test_missing_evidence_target_blocks_schedule() -> None:
    task_one = ParallelTaskSpec(
        task_id="task-one",
        owned_paths=("src/zeus_agent/security/**",),
        manual_qa_channel="script-pty",
        evidence_target=None,
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    schedule = ParallelScheduler().plan([task_one])

    assert schedule.decision == "blocked"
    assert "evidence_target:task-one:missing" in schedule.blocked_reasons


def test_missing_dependency_blocks_schedule_without_crashing() -> None:
    task_one = ParallelTaskSpec(
        task_id="task-one",
        owned_paths=("src/zeus_agent/orchestration_runtime",),
        depends_on=("missing-task",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_missing_dependency_blocks_schedule_without_crashing",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )
    task_two = ParallelTaskSpec(
        task_id="task-two",
        owned_paths=("src/zeus_agent/orchestration_runtime/models.py",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_missing_dependency_blocks_schedule_without_crashing",
        live_capable=False,
        security_decisions=(),
        subagent_depth=1,
    )

    schedule = ParallelScheduler().plan([task_one, task_two])

    assert schedule.decision == "blocked"
    assert schedule.waves == ()
    assert schedule.dry_run is True
    assert "depends_on:task-one:missing:missing-task" in schedule.blocked_reasons


def test_live_capable_task_without_live_security_decision_blocks() -> None:
    task_one = ParallelTaskSpec(
        task_id="live-task",
        owned_paths=("src/zeus_agent/security/live.py",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_live_capable_task_without_live_security_decision_blocks",
        live_capable=True,
        security_decisions=(),
        subagent_depth=1,
    )
    schedule = ParallelScheduler().plan([task_one])

    assert schedule.decision == "blocked"
    assert "security:live-task:missing_live_allow" in schedule.blocked_reasons


def test_subagent_depth_greater_than_one_blocks() -> None:
    task_one = ParallelTaskSpec(
        task_id="nested-task",
        owned_paths=("src/zeus_agent/capability_runtime",),
        manual_qa_channel="script-pty",
        evidence_target="tests/test_wave9_total_orchestration_runtime.py::test_subagent_depth_greater_than_one_blocks",
        live_capable=False,
        security_decisions=(),
        subagent_depth=2,
    )
    schedule = ParallelScheduler().plan([task_one])

    assert schedule.decision == "blocked"
    assert "subagent_depth:nested-task:exceeds_one" in schedule.blocked_reasons
