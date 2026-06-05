from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.memory_graph_runtime import MemoryGraphStore

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
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


class MemoryEntryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    selected_fact: Optional[dict[str, JsonValue]]
    fact_count: int
    quarantined_count: int
    blocked_reasons: tuple[str, ...] = ()
    memory_store_local: bool = True
    retention_policy: str = "local_review_required"
    memory_promoted: bool = False
    wiki_page_written: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class MemoryEntryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def add(
        self,
        *,
        subject: str,
        predicate: str,
        object_text: str,
        provenance_id: str,
    ) -> MemoryEntryResult:
        store = MemoryGraphStore(self.home)
        try:
            fact = store.propose_fact(
                subject=subject,
                predicate=predicate,
                object_text=object_text,
                provenance_id=provenance_id,
            )
        except ValueError:
            return self.block("missing_memory_fields")
        snapshot = store.export_snapshot()
        return _result(
            decision="recorded",
            selected_fact=fact.to_payload(),
            fact_count=int(snapshot["fact_count"]),
            quarantined_count=int(snapshot["quarantined_count"]),
        )

    def block(self, reason: str) -> MemoryEntryResult:
        snapshot = MemoryGraphStore(self.home).export_snapshot()
        return _result(
            decision="blocked",
            selected_fact=None,
            fact_count=int(snapshot["fact_count"]),
            quarantined_count=int(snapshot["quarantined_count"]),
            blocked_reasons=(reason,),
        )


def _result(
    *,
    decision: str,
    selected_fact: Optional[dict[str, JsonValue]],
    fact_count: int,
    quarantined_count: int,
    blocked_reasons: tuple[str, ...] = (),
) -> MemoryEntryResult:
    result = MemoryEntryResult(
        decision=decision,
        selected_fact=selected_fact,
        fact_count=fact_count,
        quarantined_count=quarantined_count,
        blocked_reasons=blocked_reasons,
        memory_promoted=False,
        wiki_page_written=False,
        network_opened=False,
        handler_executed=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: MemoryEntryResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
