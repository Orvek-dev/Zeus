from __future__ import annotations

from typing import Sequence

from pydantic import JsonValue

from zeus_agent.security.credentials import redact_secret_spans

from .models import JsonObject, TrajectoryExport


def export_trajectory(*, run_id: str, events: Sequence[JsonObject]) -> TrajectoryExport:
    redacted_events = tuple(_redact_event(event) for event in events)
    return TrajectoryExport(
        run_id=redact_secret_spans(run_id.strip()),
        events=redacted_events,
        event_count=len(redacted_events),
        redacted=_events_changed(tuple(events), redacted_events),
        live_production_claimed=False,
    )


def _redact_event(event: JsonObject) -> JsonObject:
    return {str(key): _redact_value(value) for key, value in event.items()}


def _redact_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return redact_secret_spans(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value


def _events_changed(before: tuple[JsonObject, ...], after: tuple[JsonObject, ...]) -> bool:
    return before != after
