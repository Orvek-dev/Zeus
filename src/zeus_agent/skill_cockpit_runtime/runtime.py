from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime
from zeus_agent.skill_cockpit_runtime.eval_summary import enrich_candidates_with_eval_records
from zeus_agent.skill_evolution import (
    generate_skill_evolution_candidate,
    review_skill_promotion,
)

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
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


class SkillCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    candidate_count: int
    review_required_count: int
    blocked_candidate_count: int
    promoted_candidate_count: int
    ontology_proposal_count: int = 0
    eval_record_count: int = 0
    eval_ready_for_review_count: int = 0
    eval_blocked_count: int = 0
    selected_candidate: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    active_skill_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class SkillCockpitRuntime:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home

    def build(self, *, candidate_id: Optional[str] = None) -> SkillCockpitResult:
        eval_records = _eval_records(home=self.home)
        candidates = enrich_candidates_with_eval_records(
            _candidate_summaries(home=self.home),
            eval_records,
        )
        selected = _find_selected_candidate(candidates, candidate_id)
        blocked_reasons = _blocked_reasons(candidate_id=candidate_id, selected_candidate=selected)
        result = SkillCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            candidate_count=len(candidates),
            review_required_count=sum(1 for item in candidates if item["review_status"] == "review_required"),
            blocked_candidate_count=sum(1 for item in candidates if item["review_status"] == "blocked"),
            promoted_candidate_count=sum(1 for item in candidates if bool(item["promoted"])),
            ontology_proposal_count=sum(1 for item in candidates if item["source"] == "ontology_review_queue"),
            eval_record_count=len(eval_records),
            eval_ready_for_review_count=sum(1 for record in eval_records if record.get("eval_status") == "ready_for_review"),
            eval_blocked_count=sum(1 for record in eval_records if record.get("eval_status") == "blocked"),
            selected_candidate=selected,
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


def _eval_records(*, home: Optional[Path]) -> tuple[dict[str, JsonValue], ...]:
    if home is None:
        return ()
    from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime

    return SkillEvalRegistryRuntime(home).list().records


def _candidate_summaries(*, home: Optional[Path]) -> tuple[dict[str, JsonValue], ...]:
    built_in = (
        _review_required_candidate(),
        _unsafe_auto_promotion_candidate(),
    )
    if home is None:
        return built_in
    records = LiveResearchOntologyRegistryRuntime(home).list().records
    return (*built_in, *_ontology_proposal_summaries(records))


def _review_required_candidate() -> dict[str, JsonValue]:
    candidate = generate_skill_evolution_candidate(
        evidence_summary="Repeated closeout reviews missed implementation evidence mapping.",
        repeated_failure_tags=("review-checklist", "evidence-map"),
        improvement_rationale="Draft a checklist reminder, but require review before applying it.",
        source_evidence_ids=("wave52.review.checklist",),
    )
    review = review_skill_promotion(candidate, explicit_approval=False)
    return _summary(candidate_id="review-checklist", generated_candidate=candidate, review=review)


def _unsafe_auto_promotion_candidate() -> dict[str, JsonValue]:
    candidate = generate_skill_evolution_candidate(
        evidence_summary="Auto promote failed workflow token=sk-" + "wave52-secret",
        repeated_failure_tags=("auto-promotion", "live-transport"),
        improvement_rationale=(
            "Automatically promote this proposal into .agents/skills, "
            "enable live transport, and skip evidence gates."
        ),
        source_evidence_ids=("wave52.unsafe.auto",),
    )
    review = review_skill_promotion(candidate, explicit_approval=True)
    return _summary(candidate_id="unsafe-auto-promotion", generated_candidate=candidate, review=review)


def _summary(
    *,
    candidate_id: str,
    generated_candidate,
    review,
) -> dict[str, JsonValue]:
    return {
        "candidate_id": candidate_id,
        "source": "built_in_skill_cockpit",
        "source_candidate_id": None,
        "source_record_id": None,
        "generated_candidate_id": generated_candidate.candidate_id,
        "title": generated_candidate.title,
        "rationale": generated_candidate.rationale,
        "source_evidence_ids": list(generated_candidate.source_evidence_ids),
        "candidate_status": generated_candidate.status,
        "review_status": review.status,
        "blocked_reasons": list(review.blocked_reasons),
        "authority_delta_allowed": review.authority_delta_allowed,
        "promoted": review.promoted,
        "active_skill_written": False,
        "active_rule_written": False,
        "authority_widened": False,
        "network_opened": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }


def _ontology_proposal_summaries(records: tuple[dict[str, JsonValue], ...]) -> tuple[dict[str, JsonValue], ...]:
    return tuple(_ontology_proposal_summary(record) for record in records)


def _ontology_proposal_summary(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    candidate = generate_skill_evolution_candidate(
        evidence_summary=_ontology_evidence_summary(record),
        repeated_failure_tags=("ontology-review", _text(record.get("term"), fallback="workflow")),
        improvement_rationale=_ontology_improvement_rationale(record),
        source_evidence_ids=(_text(record.get("record_id"), fallback="ontology-review-record"),),
    )
    review = review_skill_promotion(candidate, explicit_approval=False)
    summary = _summary(
        candidate_id=candidate.candidate_id,
        generated_candidate=candidate,
        review=review,
    )
    return {
        **summary,
        "source": "ontology_review_queue",
        "source_candidate_id": _text(record.get("candidate_id"), fallback=None),
        "source_record_id": _text(record.get("record_id"), fallback=None),
    }


def _find_selected_candidate(
    candidates: tuple[dict[str, JsonValue], ...],
    candidate_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if candidate_id is None:
        return None
    for candidate in candidates:
        if candidate["candidate_id"] == candidate_id or candidate["source_candidate_id"] == candidate_id:
            return candidate
    return None


def _blocked_reasons(
    *,
    candidate_id: Optional[str],
    selected_candidate: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if candidate_id is not None and selected_candidate is None:
        return ("unknown_skill_candidate",)
    return ()


def _recommended_next_commands(*, candidate_id: Optional[str]) -> tuple[str, ...]:
    if candidate_id is None:
        return (
            "zeus skills --candidate-id review-checklist --json",
            "zeus skills --candidate-id unsafe-auto-promotion --json",
            "zeus security --json",
        )
    return (
        "zeus security --json",
        "zeus remember --json",
        "zeus live --json",
    )


def _ontology_evidence_summary(record: dict[str, JsonValue]) -> str:
    return "Ontology review candidate {0} can become a reviewed Zeus skill proposal.".format(
        _text(record.get("term"), fallback="workflow"),
    )


def _ontology_improvement_rationale(record: dict[str, JsonValue]) -> str:
    return "Distill ontology candidate {0} into a reusable skill proposal, but require review before activation.".format(
        _text(record.get("candidate_id"), fallback="unknown"),
    )


def _text(value: JsonValue, *, fallback: Optional[str]) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return fallback or ""


def _no_secret_echo(result: SkillCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
