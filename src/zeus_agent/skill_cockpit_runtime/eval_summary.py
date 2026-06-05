from __future__ import annotations

from typing import Optional

from pydantic import JsonValue


def enrich_candidates_with_eval_records(
    candidates: tuple[dict[str, JsonValue], ...],
    eval_records: tuple[dict[str, JsonValue], ...],
) -> tuple[dict[str, JsonValue], ...]:
    return tuple(_enrich_candidate(candidate, eval_records) for candidate in candidates)


def _enrich_candidate(
    candidate: dict[str, JsonValue],
    eval_records: tuple[dict[str, JsonValue], ...],
) -> dict[str, JsonValue]:
    matching_records = _matching_records(candidate=candidate, eval_records=eval_records)
    latest = matching_records[-1] if matching_records else None
    return {
        **candidate,
        "eval_record_count": len(matching_records),
        "eval_ready_for_review_count": _status_count(matching_records, "ready_for_review"),
        "eval_blocked_count": _status_count(matching_records, "blocked"),
        "latest_eval_status": _text(_latest_value(latest, "eval_status"), fallback=None),
        "latest_eval_score": _int(_latest_value(latest, "score")),
        "latest_eval_record_id": _text(_latest_value(latest, "eval_record_id"), fallback=None),
    }


def _matching_records(
    *,
    candidate: dict[str, JsonValue],
    eval_records: tuple[dict[str, JsonValue], ...],
) -> tuple[dict[str, JsonValue], ...]:
    candidate_ids = _candidate_match_ids(candidate)
    return tuple(record for record in eval_records if _record_matches(record, candidate_ids))


def _candidate_match_ids(candidate: dict[str, JsonValue]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value
            for value in (
                _text(candidate.get("candidate_id"), fallback=None),
                _text(candidate.get("generated_candidate_id"), fallback=None),
                _text(candidate.get("source_candidate_id"), fallback=None),
            )
            if value is not None
        )
    )


def _record_matches(record: dict[str, JsonValue], candidate_ids: tuple[str, ...]) -> bool:
    return any(_text(record.get(key), fallback=None) in candidate_ids for key in _MATCH_KEYS)


def _status_count(records: tuple[dict[str, JsonValue], ...], status: str) -> int:
    return sum(1 for record in records if record.get("eval_status") == status)


def _latest_value(record: Optional[dict[str, JsonValue]], key: str) -> JsonValue:
    if record is None:
        return None
    return record.get(key)


def _text(value: JsonValue, *, fallback: Optional[str]) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _int(value: JsonValue) -> Optional[int]:
    if isinstance(value, int):
        return value
    return None


_MATCH_KEYS = ("candidate_id", "generated_candidate_id", "source_candidate_id")
