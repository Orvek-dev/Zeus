from __future__ import annotations

import json
from dataclasses import dataclass

from zeus_agent.skill_evolution.models import (
    SkillEvolutionCandidate,
    SkillPromotionReview,
    generate_skill_evolution_candidate,
    review_skill_promotion,
)


@dataclass(frozen=True)
class ProposedSkillQueueRecord:
    candidate: SkillEvolutionCandidate
    review: SkillPromotionReview

    @property
    def promoted(self) -> bool:
        return self.review.promoted

    @property
    def queued(self) -> bool:
        return self.candidate.status == "proposed_not_promoted"


class ProposedSkillQueue:
    def __init__(self) -> None:
        self._records: dict[str, ProposedSkillQueueRecord] = {}

    def queue_candidate(
        self,
        *,
        evidence_summary: str,
        source_evidence_id: str,
        improvement_rationale: str,
    ) -> ProposedSkillQueueRecord:
        candidate = generate_skill_evolution_candidate(
            evidence_summary=evidence_summary,
            improvement_rationale=improvement_rationale,
            source_evidence_ids=(source_evidence_id,),
        )
        review = review_skill_promotion(candidate, explicit_approval=False)
        record = ProposedSkillQueueRecord(candidate=candidate, review=review)
        self._records[candidate.candidate_id] = record
        return record

    def review_auto_promotion_request(self, raw_secret: str) -> SkillPromotionReview:
        candidate = generate_skill_evolution_candidate(
            evidence_summary="auto promote Wave13 proposal {0}".format(raw_secret),
            improvement_rationale="auto promote active skill and enable live transport",
            source_evidence_ids=("wave13.block.skill",),
        )
        return review_skill_promotion(candidate, explicit_approval=True)

    def records(self) -> tuple[ProposedSkillQueueRecord, ...]:
        return tuple(self._records.values())


def queue_raw_secret_present(records: tuple[ProposedSkillQueueRecord, ...], raw_secret: str) -> bool:
    serialized = json.dumps(
        [
            {
                "candidate": record.candidate.model_dump(mode="json"),
                "review": record.review.model_dump(mode="json"),
            }
            for record in records
        ],
        sort_keys=True,
    )
    return raw_secret in serialized
