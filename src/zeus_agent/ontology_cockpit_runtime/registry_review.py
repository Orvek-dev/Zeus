from __future__ import annotations

from typing import Optional

from pydantic import JsonValue

from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.wiki_runtime import render_wiki_page


def registry_summaries(
    *,
    store: MemoryGraphStore,
    records: tuple[dict[str, JsonValue], ...],
) -> tuple[dict[str, JsonValue], ...]:
    return tuple(_registry_summary(store=store, record=record) for record in records)


def _registry_summary(
    *,
    store: MemoryGraphStore,
    record: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    candidate = record.get("candidate")
    candidate_payload = candidate if isinstance(candidate, dict) else {}
    term_payload = candidate_payload.get("term")
    term = term_payload if isinstance(term_payload, dict) else {}
    term_name = _text(term.get("term"), fallback=_text(record.get("term"), fallback="unknown"))
    wiki_page = render_wiki_page(store, term_name or "unknown").to_payload()
    return {
        "candidate_id": _text(
            record.get("candidate_id"),
            fallback=_text(record.get("record_id"), fallback="unknown"),
        ),
        "record_id": _text(record.get("record_id"), fallback=None),
        "source": "live_research_ontology_registry",
        "generated_candidate_id": _text(candidate_payload.get("candidate_id"), fallback=None),
        "term": term_name,
        "definition": _text(term.get("definition"), fallback=""),
        "aliases": _string_list(term.get("aliases")),
        "rationale": _text(candidate_payload.get("rationale"), fallback=""),
        "provenance": _provenance(candidate_payload.get("provenance")),
        "candidate_status": _text(record.get("candidate_status"), fallback="proposed_not_promoted"),
        "blocked_reasons": _string_list(candidate_payload.get("blocked_reasons")),
        "promoted": bool(record.get("promoted")),
        "requested_authority_widening": bool(candidate_payload.get("requested_authority_widening")),
        "requested_live_transport": bool(candidate_payload.get("requested_live_transport")),
        "requested_rule_promotion": bool(candidate_payload.get("requested_rule_promotion")),
        "requested_team_rule_promotion": bool(candidate_payload.get("requested_team_rule_promotion")),
        "wiki_subject": term_name,
        "wiki_page": wiki_page,
        "candidate_storage_mode": _text(record.get("candidate_storage_mode"), fallback="local_review_only"),
        "wiki_page_update_written": False,
        "ontology_term_promoted": False,
        "active_rule_written": False,
        "authority_widened": False,
        "network_opened": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }


def _text(value: JsonValue, *, fallback: Optional[str]) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else fallback


def _string_list(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _provenance(value: JsonValue) -> list[dict[str, JsonValue]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, JsonValue]] = []
    for item in value:
        if isinstance(item, dict):
            refs.append(
                {
                    "source_id": _text(item.get("source_id"), fallback=""),
                    "source_type": _text(item.get("source_type"), fallback=""),
                }
            )
    return refs
