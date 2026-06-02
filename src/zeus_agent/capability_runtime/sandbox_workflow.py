from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, Sequence

from .sandbox import SandboxPolicy


class SandboxWorkflowHintType(str, Enum):
    COMMAND_BATCHING = "command_batching"
    EVIDENCE_CAPTURE_ORDERING = "evidence_capture_ordering"
    TEMP_DIR_CLEANUP = "temp_dir_cleanup"
    RETRY_IDEMPOTENCY = "retry_idempotency"


@dataclass(frozen=True)
class SandboxOptimizationHint:
    hint_type: SandboxWorkflowHintType
    reason: str | None = None


@dataclass(frozen=True)
class SandboxWorkflowStep:
    command: str
    argv: tuple[str, ...]
    decision: str
    reason: str | None = None


@dataclass(frozen=True)
class SandboxWorkflowPlan:
    steps: tuple[SandboxWorkflowStep, ...]
    optimization_hints: tuple[SandboxOptimizationHint, ...]
    optimization_count: int = 0
    blocked_reasons: tuple[str, ...] = ()
    handler_executed: bool = False
    network_opened: bool = False


class SandboxWorkflowOptimizer:
    def __init__(self, policy: SandboxPolicy | None = None):
        self.policy: SandboxPolicy = policy or SandboxPolicy()

    def optimize(
        self,
        commands: Sequence[str],
        root: Path | None = None,
    ) -> SandboxWorkflowPlan:
        sandbox_root = root.resolve() if root is not None else Path.cwd()
        steps: list[SandboxWorkflowStep] = []
        for raw_command in commands:
            decision = self.policy.decide_command(raw_command, sandbox_root)
            steps.append(
                SandboxWorkflowStep(
                    command=_normalize_command(raw_command),
                    argv=decision.argv,
                    decision=decision.decision,
                    reason=decision.reason,
                )
            )
        optimization_hints = tuple(_default_hints(steps))
        blocked_reasons = tuple(
            step.reason for step in steps if step.decision == "blocked" and step.reason is not None
        )
        return SandboxWorkflowPlan(
            steps=tuple(steps),
            optimization_hints=optimization_hints,
            optimization_count=len(optimization_hints),
            blocked_reasons=blocked_reasons,
            handler_executed=False,
            network_opened=False,
        )


def _normalize_command(raw_command: str) -> str:
    return raw_command


def _default_hints(steps: Sequence[SandboxWorkflowStep]) -> tuple[SandboxOptimizationHint, ...]:
    if not steps:
        return ()

    all_allowed = all(step.decision == "allowed" for step in steps)
    if not all_allowed:
        return ()

    return (
        SandboxOptimizationHint(
            hint_type=SandboxWorkflowHintType.COMMAND_BATCHING,
            reason="Prefer grouping commands that touch the same workspace root into one batched step.",
        ),
        SandboxOptimizationHint(
            hint_type=SandboxWorkflowHintType.EVIDENCE_CAPTURE_ORDERING,
            reason="Capture command stdout/stderr in sequence and persist before cleanup.",
        ),
        SandboxOptimizationHint(
            hint_type=SandboxWorkflowHintType.TEMP_DIR_CLEANUP,
            reason="Remove temporary directories created for workflow execution after all commands complete.",
        ),
        SandboxOptimizationHint(
            hint_type=SandboxWorkflowHintType.RETRY_IDEMPOTENCY,
            reason="Emit stable idempotency keys and retry budget before rerunning local commands.",
        ),
    )


__all__: Final = (
    "SandboxWorkflowHintType",
    "SandboxOptimizationHint",
    "SandboxWorkflowOptimizer",
    "SandboxWorkflowPlan",
    "SandboxWorkflowStep",
)
