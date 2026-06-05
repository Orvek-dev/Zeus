from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_research_ontology_registry_runtime import LiveResearchOntologyRegistryRuntime
from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.ontology_runtime import (
    OntologyCandidate,
    OntologyCandidateBuilder,
    OntologyProvenanceRef,
    OntologyTerm,
)
from zeus_agent.ontology_cockpit_runtime.registry_review import registry_summaries
from zeus_agent.wiki_runtime import render_wiki_page

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


class OntologyCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    candidate_count: int
    proposed_candidate_count: int
    blocked_candidate_count: int
    promoted_candidate_count: int
    registry_record_count: int = 0
    review_queue_count: int = 0
    selected_candidate: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    memory_store_local: bool = True
    candidate_storage_mode: Literal["proposed_review_only"] = "proposed_review_only"
    wiki_page_update_written: bool = False
    ontology_term_promoted: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class OntologyCockpitRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def build(self, *, candidate_id: Optional[str] = None) -> OntologyCockpitResult:
        store = MemoryGraphStore(self.home)
        registry_records = LiveResearchOntologyRegistryRuntime(self.home).list().records
        candidates = _candidate_summaries(store, registry_records=registry_records)
        selected = _find_selected_candidate(candidates, candidate_id)
        blocked_reasons = _blocked_reasons(candidate_id=candidate_id, selected_candidate=selected)
        result = OntologyCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            candidate_count=len(candidates),
            proposed_candidate_count=sum(
                1 for item in candidates if item["candidate_status"] == "proposed_not_promoted"
            ),
            blocked_candidate_count=sum(1 for item in candidates if item["candidate_status"] == "blocked"),
            promoted_candidate_count=sum(1 for item in candidates if bool(item["promoted"])),
            registry_record_count=len(registry_records),
            review_queue_count=sum(
                1 for item in candidates if item["source"] == "live_research_ontology_registry"
            ),
            selected_candidate=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(candidate_id=candidate_id),
            memory_store_local=True,
            wiki_page_update_written=False,
            ontology_term_promoted=False,
            active_rule_written=False,
            authority_widened=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _candidate_summaries(
    store: MemoryGraphStore,
    *,
    registry_records: tuple[dict[str, JsonValue], ...],
) -> tuple[dict[str, JsonValue], ...]:
    return (
        _summary(
            candidate_id="objective-contract",
            candidate=_objective_contract_candidate(),
            store=store,
        ),
        _summary(
            candidate_id="unsafe-rule-promotion",
            candidate=_unsafe_rule_promotion_candidate(),
            store=store,
        ),
        *registry_summaries(store=store, records=registry_records),
    )


def _objective_contract_candidate() -> OntologyCandidate:
    builder = OntologyCandidateBuilder()
    return builder.build_candidate(
        term=OntologyTerm(
            term="objective_contract",
            definition="Goal, authority, evidence, and stop-condition contract.",
            aliases=("objective", "contract"),
        ),
        rationale="Observed repeated planning traces need a stable objective contract term.",
        provenance=(
            OntologyProvenanceRef(source_type="research", source_id="research-wave53-objective"),
            OntologyProvenanceRef(source_type="evidence", source_id="evidence-wave53-objective"),
        ),
    )


def _unsafe_rule_promotion_candidate() -> OntologyCandidate:
    builder = OntologyCandidateBuilder()
    return builder.build_candidate(
        term=OntologyTerm(
            term="unreviewed_rule_promotion",
            definition="A proposal that tries to promote ontology terms into rules without review.",
        ),
        rationale="Observed proposal tried to promote an ontology term into active rules.",
        provenance=(OntologyProvenanceRef(source_type="evidence", source_id="evidence-wave53-unsafe"),),
        requested_rule_promotion=True,
        requested_team_rule_promotion=True,
    )


def _summary(
    *,
    candidate_id: str,
    candidate: OntologyCandidate,
    store: MemoryGraphStore,
) -> dict[str, JsonValue]:
    wiki_page = render_wiki_page(store, candidate.term.term).to_payload()
    return {
        "candidate_id": candidate_id,
        "record_id": None,
        "source": "built_in_ontology_cockpit",
        "generated_candidate_id": candidate.candidate_id,
        "term": candidate.term.term,
        "definition": candidate.term.definition,
        "aliases": list(candidate.term.aliases),
        "rationale": candidate.rationale,
        "provenance": [
            {"source_id": ref.source_id, "source_type": ref.source_type}
            for ref in candidate.provenance
        ],
        "candidate_status": candidate.status,
        "blocked_reasons": list(candidate.blocked_reasons),
        "promoted": candidate.promoted,
        "requested_authority_widening": candidate.requested_authority_widening,
        "requested_live_transport": candidate.requested_live_transport,
        "requested_rule_promotion": candidate.requested_rule_promotion,
        "requested_team_rule_promotion": candidate.requested_team_rule_promotion,
        "wiki_subject": candidate.term.term,
        "wiki_page": wiki_page,
        "candidate_storage_mode": "proposed_review_only",
        "wiki_page_update_written": False,
        "ontology_term_promoted": False,
        "active_rule_written": False,
        "authority_widened": False,
        "network_opened": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }


def _find_selected_candidate(
    candidates: tuple[dict[str, JsonValue], ...],
    candidate_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if candidate_id is None:
        return None
    for candidate in candidates:
        if candidate["candidate_id"] == candidate_id:
            return candidate
    return None


def _blocked_reasons(
    *,
    candidate_id: Optional[str],
    selected_candidate: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if candidate_id is not None and selected_candidate is None:
        return ("unknown_ontology_candidate",)
    return ()


def _recommended_next_commands(*, candidate_id: Optional[str]) -> tuple[str, ...]:
    if candidate_id is None:
        return (
            "zeus ontology --candidate-id objective-contract --json",
            "zeus remember --subject objective_contract --json",
            "zeus wiki-page --subject objective_contract --json",
        )
    return (
        "zeus remember --subject objective_contract --json",
        "zeus skills --json",
        "zeus security --json",
    )


def _no_secret_echo(result: OntologyCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
