from __future__ import annotations

from dataclasses import dataclass

from pydantic import JsonValue

JsonObject = dict[str, JsonValue]


@dataclass(frozen=True)
class WikiPage:
    subject: str
    body: str
    fact_count: int

    def to_payload(self) -> JsonObject:
        return {
            "subject": self.subject,
            "body": self.body,
            "fact_count": self.fact_count,
            "live_production_claimed": False,
        }
