from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NodeState(str, Enum):
    pending = "pending"
    running = "running"
    waiting_approval = "waiting_approval"
    succeeded = "succeeded"
    failed = "failed"
    rolled_back = "rolled_back"
    skipped = "skipped"


class RunStatus(str, Enum):
    running = "running"
    waiting_approval = "waiting_approval"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"


_TERMINAL_NODE_STATES = frozenset(
    {NodeState.succeeded, NodeState.failed, NodeState.rolled_back, NodeState.skipped}
)


class RunState(BaseModel):
    """Mutable, persisted execution state for one workflow run.

    Deliberately NOT frozen: this is working state advanced step-by-step and
    serialized to the state store, not a value object. The candidate DAG is
    carried as JSON so a suspended run can be resumed in a fresh process.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    objective_id: str
    candidate_id: str
    candidate_json: str
    node_states: dict[str, NodeState]
    node_receipts: dict[str, str] = Field(default_factory=dict)
    status: RunStatus = RunStatus.running
    required_criteria: tuple[str, ...] = ()
    budget_limit: int = Field(default=0, ge=0)
    budget_spent_units: int = Field(default=0, ge=0)
    blocked_reason: Optional[str] = None

    def is_node_terminal(self, node_id: str) -> bool:
        return self.node_states.get(node_id) in _TERMINAL_NODE_STATES
