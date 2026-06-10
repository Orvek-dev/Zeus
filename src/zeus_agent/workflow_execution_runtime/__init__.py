"""Governed Workflow Execution Runtime (M1) — the spine's missing heart.

Takes a verified workflow DAG and actually moves it: topological execution,
per-node dispatch through the single GovernedExecutionDispatcher chokepoint,
suspend at approval gates / resume after approval, caused_by evidence edges,
rollback receipts on failure, earned-trust recording per node, and completion
judged by evidence alone. Replaces the loopback executor mock.
"""

from __future__ import annotations

from .models import NodeState, RunState, RunStatus
from .runtime import CapabilityApprovals, Verifier, WorkflowExecutionRuntime
from .state_store import WorkflowExecutionStateStore

__all__ = [
    "CapabilityApprovals",
    "NodeState",
    "RunState",
    "RunStatus",
    "Verifier",
    "WorkflowExecutionRuntime",
    "WorkflowExecutionStateStore",
]
