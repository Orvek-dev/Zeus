from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_evolution import generate_skill_evolution_candidate
from zeus_agent.skill_evolution import review_skill_promotion
from zeus_agent.skill_learning_runtime.models import SkillLearningResult

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


class SkillLearningRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def build(self, *, candidate_id: Optional[str] = None) -> SkillLearningResult:
        registry = SkillEvalRegistryRuntime(self.home).list()
        learnings = _learning_summaries(registry.records)
        selected = _find_selected_learning(learnings, candidate_id)
        blocked_reasons = _blocked_reasons(candidate_id=candidate_id, selected_learning=selected)
        result = SkillLearningResult(
            decision="blocked" if blocked_reasons else "report",
            eval_record_count=registry.record_count,
            learning_candidate_count=len(learnings),
            ready_learning_count=sum(1 for item in learnings if item["eval_status"] == "ready_for_review"),
            blocked_learning_count=sum(1 for item in learnings if item["eval_status"] == "blocked"),
            review_required_count=sum(1 for item in learnings if item["review_status"] == "review_required"),
            promoted_candidate_count=sum(1 for item in learnings if bool(item["promoted"])),
            selected_learning=selected,
            learning_candidates=learnings,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(candidate_id=candidate_id),
            active_skill_written=False,
            active_rule_written=False,
            authority_widened=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _learning_summaries(records: tuple[dict[str, JsonValue], ...]) -> tuple[dict[str, JsonValue], ...]:
    return tuple(_learning_summary(record) for record in records)


def _learning_summary(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    candidate_id = _text(record.get("candidate_id"), fallback="unknown")
    eval_status = _text(record.get("eval_status"), fallback="blocked")
    score = _int(record.get("score"))
    candidate = generate_skill_evolution_candidate(
        evidence_summary=_evidence_summary(record=record, candidate_id=candidate_id, eval_status=eval_status, score=score),
        repeated_failure_tags=("skill-eval", eval_status, candidate_id),
        improvement_rationale=_improvement_rationale(candidate_id=candidate_id, eval_status=eval_status),
        source_evidence_ids=(_source_evidence_id(record),),
    )
    review = review_skill_promotion(candidate, explicit_approval=False)
    return {
        "candidate_id": candidate_id,
        "source": "skill_eval_registry",
        "learning_candidate_id": candidate.candidate_id,
        "eval_record_id": _text(record.get("eval_record_id"), fallback=None),
        "eval_ref": _text(record.get("eval_ref"), fallback=None),
        "eval_status": eval_status,
        "eval_score": score,
        "eval_blocked_reasons": _text_list(record.get("blocked_reasons")),
        "title": candidate.title,
        "rationale": candidate.rationale,
        "source_evidence_ids": list(candidate.source_evidence_ids),
        "candidate_status": candidate.status,
        "review_status": review.status,
        "blocked_reasons": list(review.blocked_reasons),
        "authority_delta_allowed": False,
        "promoted": False,
        "active_skill_written": False,
        "active_rule_written": False,
        "authority_widened": False,
        "network_opened": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }


def _find_selected_learning(
    learnings: tuple[dict[str, JsonValue], ...],
    candidate_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if candidate_id is None:
        return None
    for learning in learnings:
        if candidate_id in _learning_match_ids(learning):
            return learning
    return None


def _learning_match_ids(learning: dict[str, JsonValue]) -> tuple[str, ...]:
    return tuple(
        item
        for item in (
            _text(learning.get("candidate_id"), fallback=None),
            _text(learning.get("learning_candidate_id"), fallback=None),
            _text(learning.get("eval_record_id"), fallback=None),
        )
        if item is not None
    )


def _blocked_reasons(
    *,
    candidate_id: Optional[str],
    selected_learning: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if candidate_id is not None and selected_learning is None:
        return ("unknown_skill_learning_candidate",)
    return ()


def _recommended_next_commands(*, candidate_id: Optional[str]) -> tuple[str, ...]:
    if candidate_id is None:
        return ("zeus skill-learnings --candidate-id <candidate-id> --json", "zeus skills --json")
    return ("zeus skills --candidate-id {0} --json".format(candidate_id), "zeus skill-eval-records --json")


def _evidence_summary(
    *,
    record: dict[str, JsonValue],
    candidate_id: str,
    eval_status: str,
    score: Optional[int],
) -> str:
    record_id = _source_evidence_id(record)
    return "Skill eval record {0} shows candidate {1} status {2} with score {3}.".format(
        record_id,
        candidate_id,
        eval_status,
        _score_text(score),
    )


def _improvement_rationale(*, candidate_id: str, eval_status: str) -> str:
    return "Create a reviewed Prometheus learning candidate for {0} from eval status {1}.".format(
        candidate_id,
        eval_status,
    )


def _source_evidence_id(record: dict[str, JsonValue]) -> str:
    return _text(record.get("eval_record_id"), fallback=None) or _text(record.get("eval_ref"), fallback="skill-eval-record")


def _score_text(score: Optional[int]) -> str:
    if score is None:
        return "unknown"
    return str(score)


def _text(value: JsonValue, *, fallback: Optional[str]) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _int(value: JsonValue) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _text_list(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _no_secret_echo(result: SkillLearningResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
