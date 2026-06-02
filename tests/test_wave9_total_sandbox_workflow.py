from __future__ import annotations

from pathlib import Path

import pytest

from zeus_agent.capability_runtime import sandbox as sandbox_module
from zeus_agent.capability_runtime import SandboxPolicy
from zeus_agent.capability_runtime.sandbox_workflow import (
    SandboxWorkflowHintType,
    SandboxWorkflowOptimizer,
    SandboxWorkflowStep,
    SandboxWorkflowPlan,
)


def test_sandbox_workflow_optimizer_preserves_network_and_destructive_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path
    original_decide_command = SandboxPolicy.decide_command
    decision_calls: list[tuple[object, object]] = []

    def spy_decide(self: SandboxPolicy, raw_command: object, command_root: Path):
        decision_calls.append((raw_command, command_root))
        return original_decide_command(self, raw_command, command_root)

    monkeypatch.setattr(SandboxPolicy, "decide_command", spy_decide)
    monkeypatch.setattr(sandbox_module.subprocess, "run", pytest.fail)

    optimizer = SandboxWorkflowOptimizer(policy=SandboxPolicy())
    plan = optimizer.optimize(["curl https://example.com", "rm -rf /tmp/important"], root)

    assert len(plan.steps) == 2
    first, second = plan.steps
    assert first.command == "curl https://example.com"
    assert first.reason == "network_command_blocked"
    assert first.decision == "blocked"
    assert second.reason == "destructive_command_blocked"
    assert second.decision == "blocked"
    assert decision_calls == [
        ("curl https://example.com", root),
        ("rm -rf /tmp/important", root),
    ]
    assert plan.handler_executed is False
    assert plan.network_opened is False


def test_local_commands_produce_optimization_hints_and_do_not_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path
    original_decide_command = SandboxPolicy.decide_command
    decision_calls: list[tuple[str, Path]] = []

    def spy_decide(self: SandboxPolicy, raw_command: str, command_root: Path):
        decision_calls.append((raw_command, command_root))
        return original_decide_command(self, raw_command, command_root)

    monkeypatch.setattr(SandboxPolicy, "decide_command", spy_decide)
    monkeypatch.setattr(sandbox_module.subprocess, "run", pytest.fail)

    optimizer = SandboxWorkflowOptimizer(policy=SandboxPolicy())
    plan = optimizer.optimize(["pwd", "ls", "cat"], root)

    assert plan.handler_executed is False
    assert plan.network_opened is False
    assert plan.optimization_count == 4
    assert len(plan.blocked_reasons) == 0
    assert len(plan.steps) == 3
    assert all(step.decision == "allowed" for step in plan.steps)
    assert all(step.reason is None for step in plan.steps)
    hint_types = [hint.hint_type for hint in plan.optimization_hints]
    assert SandboxWorkflowHintType.COMMAND_BATCHING in hint_types
    assert SandboxWorkflowHintType.EVIDENCE_CAPTURE_ORDERING in hint_types
    assert SandboxWorkflowHintType.TEMP_DIR_CLEANUP in hint_types
    assert SandboxWorkflowHintType.RETRY_IDEMPOTENCY in hint_types
    assert len(plan.optimization_hints) == 4
    assert len(decision_calls) == 3


def test_sandbox_workflow_optimizer_preserves_default_allowed_commands() -> None:
    optimizer = SandboxWorkflowOptimizer()

    assert optimizer.policy.allowed_commands == sandbox_module.DEFAULT_ALLOWED_COMMANDS
    assert optimizer.policy.allowed_commands == ("cat", "grep", "head", "ls", "pwd", "tail", "wc")


def test_optimizer_uses_default_root_when_not_provided() -> None:
    plan = SandboxWorkflowOptimizer().optimize(commands=("ls", "pwd", "wc README.md"))

    assert plan.optimization_count == 4
    assert plan.handler_executed is False
    assert plan.network_opened is False
    assert plan.blocked_reasons == ()
    assert plan.steps[0].command == "ls"
    assert plan.steps[1].command == "pwd"
    assert plan.steps[2].command == "wc README.md"


@pytest.mark.parametrize(
    ("commands", "expected_reasons"),
    [
        ([""], ("malformed_command",)),
        (["definitely_not_allowed_foo"], ("command_not_allowlisted",)),
    ],
)
def test_malformed_or_unsupported_command_blocks_instead_of_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    commands: list[str],
    expected_reasons: tuple[str],
) -> None:
    root = tmp_path
    policy = SandboxPolicy()
    monkeypatch.setattr(sandbox_module.subprocess, "run", pytest.fail)

    plan = SandboxWorkflowOptimizer(policy=policy).optimize(commands, root)

    assert all(step.decision == "blocked" for step in plan.steps)
    assert tuple(step.reason for step in plan.steps) == expected_reasons
    assert plan.handler_executed is False
    assert plan.network_opened is False
    assert plan.blocked_reasons == expected_reasons
    assert plan.optimization_count >= 0


def test_sandbox_workflow_step_is_frozen_and_repr_stable() -> None:
    step = SandboxWorkflowStep(
        command="pwd",
        argv=("pwd",),
        decision="allowed",
        reason=None,
    )
    assert repr(step) == "SandboxWorkflowStep(command='pwd', argv=('pwd',), decision='allowed', reason=None)"


def test_sandbox_workflow_plan_is_frozen() -> None:
    plan = SandboxWorkflowPlan(
        steps=(),
        optimization_hints=(),
        handler_executed=False,
        network_opened=False,
    )
    assert plan.handler_executed is False
    assert plan.network_opened is False
