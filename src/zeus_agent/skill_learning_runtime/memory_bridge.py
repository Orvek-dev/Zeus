from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.skill_learning_runtime.models import SkillLearningMemoryResult
from zeus_agent.skill_learning_runtime.runtime import SkillLearningRuntime

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


class SkillLearningMemoryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def record(self, *, candidate_id: str) -> SkillLearningMemoryResult:
        learning = SkillLearningRuntime(self.home).build(candidate_id=candidate_id)
        selected = learning.selected_learning
        if learning.decision == "blocked" or selected is None:
            return _result(
                decision="blocked",
                home=self.home,
                selected_learning=None,
                selected_fact=None,
                learning_candidate_count=learning.learning_candidate_count,
                blocked_reasons=learning.blocked_reasons or ("unknown_skill_learning_candidate",),
            )
        store = MemoryGraphStore(self.home)
        fact = store.propose_fact(
            subject="Prometheus",
            predicate="skill_eval_learning_candidate",
            object_text=_object_text(selected),
            provenance_id=_provenance_id(selected),
        )
        return _result(
            decision="recorded",
            home=self.home,
            selected_learning=selected,
            selected_fact=fact.to_payload(),
            learning_candidate_count=learning.learning_candidate_count,
        )


def _result(
    *,
    decision: str,
    home: Path,
    selected_learning: Optional[dict[str, JsonValue]],
    selected_fact: Optional[dict[str, JsonValue]],
    learning_candidate_count: int,
    blocked_reasons: tuple[str, ...] = (),
) -> SkillLearningMemoryResult:
    snapshot = MemoryGraphStore(home).export_snapshot()
    result = SkillLearningMemoryResult(
        decision=decision,
        selected_learning=selected_learning,
        selected_fact=selected_fact,
        learning_candidate_count=learning_candidate_count,
        fact_count=int(snapshot["fact_count"]),
        quarantined_count=int(snapshot["quarantined_count"]),
        blocked_reasons=blocked_reasons,
        memory_promoted=False,
        wiki_page_written=False,
        active_skill_written=False,
        active_rule_written=False,
        authority_widened=False,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _object_text(learning: dict[str, JsonValue]) -> str:
    return (
        "candidate={0}; eval_status={1}; review_status={2}; "
        "learning_candidate={3}; promoted=false"
    ).format(
        _text(learning.get("candidate_id"), fallback="unknown"),
        _text(learning.get("eval_status"), fallback="unknown"),
        _text(learning.get("review_status"), fallback="unknown"),
        _text(learning.get("learning_candidate_id"), fallback="unknown"),
    )


def _provenance_id(learning: dict[str, JsonValue]) -> str:
    return (
        _text(learning.get("eval_record_id"), fallback=None)
        or _text(learning.get("eval_ref"), fallback=None)
        or _text(learning.get("learning_candidate_id"), fallback="skill-learning")
    )


def _text(value: JsonValue, *, fallback: Optional[str]) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _no_secret_echo(result: SkillLearningMemoryResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
