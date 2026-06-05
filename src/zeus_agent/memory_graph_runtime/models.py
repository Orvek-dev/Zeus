from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

JsonObject = dict[str, JsonValue]
MemoryFactStatus = Literal["proposed", "quarantined", "deleted"]


@dataclass(frozen=True)
class MemoryFact:
    fact_id: str
    subject: str
    predicate: str
    object_text: str
    provenance_id: str
    status: MemoryFactStatus
    blocked_reasons: tuple[str, ...]
    created_at: str
    updated_at: str

    def to_payload(self) -> JsonObject:
        return {
            "fact_id": self.fact_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object_text": self.object_text,
            "provenance_id": self.provenance_id,
            "status": self.status,
            "blocked_reasons": list(self.blocked_reasons),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "live_production_claimed": False,
        }
