from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.orchestration_runtime import DynamicWorkflowCompiler
from zeus_agent.orchestration_runtime import WorkflowCompileRequest
from zeus_agent.workflow_learning_runtime.models import WorkflowCritiqueMemoryResult

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class WorkflowCritiqueMemoryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def record(self, *, request: WorkflowCompileRequest) -> WorkflowCritiqueMemoryResult:
        plan = DynamicWorkflowCompiler().compile(request)
        checkpoint = plan.critique_checkpoint.model_dump(mode="json")
        if plan.decision == "blocked":
            return _result(
                decision="blocked",
                home=self.home,
                selected_checkpoint=checkpoint,
                selected_fact=None,
                blocked_reasons=plan.blocked_reasons,
            )
        store = MemoryGraphStore(self.home)
        fact = store.propose_fact(
            subject="Olympus",
            predicate="workflow_critique_checkpoint",
            object_text=_object_text(checkpoint),
            provenance_id=_provenance_id(checkpoint),
        )
        return _result(
            decision="recorded",
            home=self.home,
            selected_checkpoint=checkpoint,
            selected_fact=fact.to_payload(),
        )


def _result(
    *,
    decision: str,
    home: Path,
    selected_checkpoint: Optional[dict[str, JsonValue]],
    selected_fact: Optional[dict[str, JsonValue]],
    blocked_reasons: tuple[str, ...] = (),
) -> WorkflowCritiqueMemoryResult:
    snapshot = MemoryGraphStore(home).export_snapshot()
    result = WorkflowCritiqueMemoryResult(
        decision=decision,
        selected_checkpoint=selected_checkpoint,
        selected_fact=selected_fact,
        fact_count=int(snapshot["fact_count"]),
        quarantined_count=int(snapshot["quarantined_count"]),
        blocked_reasons=blocked_reasons,
        memory_promoted=False,
        wiki_page_written=False,
        authority_widened=False,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _object_text(checkpoint: dict[str, JsonValue]) -> str:
    return (
        "objective={0}; adaptation={1}; evidence={2}; lesson={3}; memory_write=false"
    ).format(
        _text(checkpoint.get("objective_id"), fallback="unknown"),
        _text(checkpoint.get("adaptation_decision"), fallback="unknown"),
        _text(checkpoint.get("evidence_target"), fallback="unknown"),
        _text(checkpoint.get("reusable_lesson_candidate"), fallback="unknown"),
    )


def _provenance_id(checkpoint: dict[str, JsonValue]) -> str:
    return _text(checkpoint.get("evidence_target"), fallback="workflow-critique-checkpoint")


def _text(value: JsonValue, *, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _no_secret_echo(result: WorkflowCritiqueMemoryResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
