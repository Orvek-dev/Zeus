"""Append-only local event log."""

from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.paths import events_dir, init_home
from zeus_agent.schemas.trace_event import TraceEvent
from zeus_agent.storage.jsonio import append_private_jsonl


class EventLog:
    def __init__(self, home: Path | None = None) -> None:
        paths = init_home(home)
        self.path = events_dir(paths["home"]) / "trace.jsonl"

    def append(self, event: TraceEvent) -> Path:
        return append_private_jsonl(self.path, event.model_dump(mode="json"))

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        events: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events
