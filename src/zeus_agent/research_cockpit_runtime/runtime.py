from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.research_runtime import build_research_brief

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


class ResearchCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    source_lane_count: int
    source_pin_required_count: int
    live_enabled_count: int
    source_lanes: tuple[dict[str, JsonValue], ...]
    brief_preview: dict[str, JsonValue]
    selected_source: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    client_constructed: bool = False
    subprocess_started: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ResearchCockpitRuntime:
    def build(
        self,
        *,
        source_id: Optional[str] = None,
        query: str = "agent workflow research",
        objective_id: str = "wave55.research",
    ) -> ResearchCockpitResult:
        lanes = _source_lanes()
        selected = _find_selected_source(lanes, source_id)
        blocked_reasons = _blocked_reasons(source_id=source_id, selected_source=selected)
        brief_preview = _brief_preview(query=query, objective_id=objective_id)
        result = ResearchCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            source_lane_count=len(lanes),
            source_pin_required_count=sum(1 for item in lanes if bool(item["requires_source_pin"])),
            live_enabled_count=sum(1 for item in lanes if bool(item["live_adapter_enabled"])),
            source_lanes=lanes,
            brief_preview=brief_preview,
            selected_source=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(source_id=source_id),
            credential_material_accessed=False,
            network_opened=bool(brief_preview["network_opened"]),
            handler_executed=bool(brief_preview["handler_executed"]),
            client_constructed=bool(brief_preview["client_constructed"]),
            subprocess_started=bool(brief_preview["subprocess_started"]),
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _source_lanes() -> tuple[dict[str, JsonValue], ...]:
    return (
        _source_lane(
            source_id="web",
            source_kind="web_source_pin",
            provider_id="web.fake",
            current_mode="fake_pinned_provider",
        ),
        _source_lane(
            source_id="github",
            source_kind="github_source_pin",
            provider_id="github.fake",
            current_mode="fake_pinned_provider",
        ),
        _source_lane(
            source_id="developer-docs",
            source_kind="local_doc",
            provider_id="manual.docs",
            current_mode="planned_manual_source_pin",
        ),
        _source_lane(
            source_id="community",
            source_kind="web_source_pin",
            provider_id="manual.community",
            current_mode="planned_review_required",
        ),
    )


def _source_lane(
    *,
    source_id: str,
    source_kind: str,
    provider_id: str,
    current_mode: str,
) -> dict[str, JsonValue]:
    return {
        "source_id": source_id,
        "source_kind": source_kind,
        "provider_id": provider_id,
        "current_mode": current_mode,
        "requires_source_pin": True,
        "freshness_required": "fresh",
        "live_adapter_enabled": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }


def _brief_preview(*, query: str, objective_id: str) -> dict[str, JsonValue]:
    payload = build_research_brief(objective_id=objective_id, query=query)
    return json.loads(json.dumps(payload, sort_keys=True))


def _find_selected_source(
    lanes: tuple[dict[str, JsonValue], ...],
    source_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if source_id is None:
        return None
    for lane in lanes:
        if lane["source_id"] == source_id:
            return lane
    return None


def _blocked_reasons(
    *,
    source_id: Optional[str],
    selected_source: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if source_id is not None and selected_source is None:
        return ("unknown_research_source",)
    return ()


def _recommended_next_commands(*, source_id: Optional[str]) -> tuple[str, ...]:
    if source_id is None:
        return (
            "zeus research --source github --query <query> --json",
            "zeus research-brief --query <query> --json",
            "zeus live --json",
        )
    return (
        "zeus research-brief --query <query> --json",
        "zeus ontology --json",
        "zeus security --json",
    )


def _no_secret_echo(result: ResearchCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
