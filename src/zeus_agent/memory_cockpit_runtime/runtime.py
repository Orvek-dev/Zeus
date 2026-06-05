from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.memory_graph_runtime import MemoryGraphStore
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


class MemoryCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report"]
    fact_count: int
    quarantined_count: int
    selected_subject: Optional[str] = None
    wiki_page: Optional[dict[str, JsonValue]] = None
    memory_store_local: bool = True
    retention_policy: Literal["local_review_required"] = "local_review_required"
    recommended_next_commands: tuple[str, ...]
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class MemoryCockpitRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def build(self, *, subject: Optional[str] = None) -> MemoryCockpitResult:
        store = MemoryGraphStore(self.home)
        snapshot = store.export_snapshot()
        selected_subject = _optional_text(subject)
        wiki_page = _wiki_page(store, selected_subject)
        result = MemoryCockpitResult(
            decision="report",
            fact_count=int(snapshot["fact_count"]),
            quarantined_count=int(snapshot["quarantined_count"]),
            selected_subject=selected_subject,
            wiki_page=wiki_page,
            recommended_next_commands=_recommended_next_commands(subject=selected_subject),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _wiki_page(
    store: MemoryGraphStore,
    subject: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if subject is None:
        return None
    return render_wiki_page(store, subject).to_payload()


def _optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    return normalized


def _recommended_next_commands(*, subject: Optional[str]) -> tuple[str, ...]:
    if subject is None:
        return (
            "zeus memory-fact-add",
            "zeus remember --subject <subject> --json",
            "zeus wiki-page --subject <subject> --json",
        )
    return (
        "zeus wiki-page --subject {0} --json".format(subject),
        "zeus memory-fact-add",
        "zeus remember --json",
    )


def _no_secret_echo(result: MemoryCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
