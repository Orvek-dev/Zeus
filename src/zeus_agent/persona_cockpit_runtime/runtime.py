from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.entry_runtime import entry_status_payload

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


class PersonaCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    persona_id: Literal["zeus"] = "zeus"
    display_name: Literal["Zeus"] = "Zeus"
    tagline: Literal["Goal-oriented AI agent"] = "Goal-oriented AI agent"
    default_call_response: Literal["Zeus is here."] = "Zeus is here."
    korean_call_response: Literal["네, Zeus입니다."] = "네, Zeus입니다."
    profile_count: int
    session_count: int
    provider_profile_count: int
    selected_profile: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    chat_turn_started: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class PersonaCockpitRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def build(self, *, profile: Optional[str] = None) -> PersonaCockpitResult:
        status = entry_status_payload(self.home)
        profiles = _profiles()
        selected = _find_selected_profile(profiles, profile)
        blocked_reasons = _blocked_reasons(profile=profile, selected_profile=selected)
        result = PersonaCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            profile_count=len(profiles),
            session_count=int(status["session_count"]),
            provider_profile_count=int(status["provider_profile_count"]),
            selected_profile=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(profile=profile),
            chat_turn_started=False,
            authority_widened=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _profiles() -> tuple[dict[str, JsonValue], ...]:
    return (
        _profile("chat", objective_mode_active=False, memory_mode=False, live_mode=False),
        _profile("research", objective_mode_active=False, memory_mode=False, live_mode=False),
        _profile("work", objective_mode_active=True, memory_mode=False, live_mode=False),
        _profile("live", objective_mode_active=True, memory_mode=False, live_mode=True),
        _profile("strict", objective_mode_active=True, memory_mode=False, live_mode=False),
        _profile("remember", objective_mode_active=False, memory_mode=True, live_mode=False),
        _profile("improve", objective_mode_active=True, memory_mode=True, live_mode=False),
    )


def _profile(
    profile: str,
    *,
    objective_mode_active: bool,
    memory_mode: bool,
    live_mode: bool,
) -> dict[str, JsonValue]:
    return {
        "profile": profile,
        "objective_mode_active": objective_mode_active,
        "memory_mode": memory_mode,
        "live_mode": live_mode,
        "authority_required_for_tools": True,
        "live_transport_default": "blocked",
        "human_approval_required_for_risk": True,
        "chat_turn_started": False,
        "network_opened": False,
        "live_production_claimed": False,
    }


def _find_selected_profile(
    profiles: tuple[dict[str, JsonValue], ...],
    profile: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if profile is None:
        return None
    for item in profiles:
        if item["profile"] == profile:
            return item
    return None


def _blocked_reasons(
    *,
    profile: Optional[str],
    selected_profile: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if profile is not None and selected_profile is None:
        return ("unknown_persona_profile",)
    return ()


def _recommended_next_commands(*, profile: Optional[str]) -> tuple[str, ...]:
    if profile is None:
        return (
            "zeus persona --profile work --json",
            "zeus zeus-chat --message 'hello Zeus' --json",
            "zeus platform --json",
        )
    return (
        "zeus zeus-chat --message 'hello Zeus' --json",
        "zeus platform --json",
        "zeus live --json",
    )


def _no_secret_echo(result: PersonaCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
