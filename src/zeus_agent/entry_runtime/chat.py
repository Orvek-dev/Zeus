from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from zeus_agent.model_runtime.provider_catalog import get_provider_profile
from zeus_agent.model_settings_runtime import ModelSettingsRuntime
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.session_runtime import SessionStore


def default_zeus_home() -> Path:
    return Path.home() / ".zeus"


@dataclass(frozen=True)
class ChatTurnResult:
    session_id: str
    profile: str
    provider_id: str
    model_id: str
    user_message: str
    assistant_message: str
    objective_mode_active: bool
    live_production_claimed: bool
    raw_secret_echoed: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "profile": self.profile,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "objective_mode_active": self.objective_mode_active,
            "live_production_claimed": self.live_production_claimed,
            "raw_secret_echoed": self.raw_secret_echoed,
        }


class ZeusChatRuntime:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home or default_zeus_home()
        self.store = SessionStore(self.home)

    def run_turn(
        self,
        *,
        message: str,
        session_id: str = "default",
        provider_id: str | None = None,
        profile: str = "chat",
    ) -> ChatTurnResult:
        normalized = redact_secret_spans(message.strip())
        if normalized == "":
            raise ValueError("empty_message")
        preference = ModelSettingsRuntime(self.home).show() if provider_id is None else None
        selected_provider_id = provider_id if provider_id is not None else preference.provider_id
        provider = get_provider_profile(selected_provider_id)
        selected_model_id = provider.default_model if preference is None else preference.model_id
        session = self.store.ensure_session(
            session_id=session_id,
            profile=profile,
            provider_id=provider.provider_id,
            title=_title_from_message(normalized),
        )
        self.store.append_message(
            session_id=session.session_id,
            role="user",
            content=normalized,
        )
        assistant = _assistant_reply(normalized, provider.display_name)
        self.store.append_message(
            session_id=session.session_id,
            role="assistant",
            content=assistant,
        )
        return ChatTurnResult(
            session_id=session.session_id,
            profile=profile,
            provider_id=provider.provider_id,
            model_id=selected_model_id,
            user_message=normalized,
            assistant_message=assistant,
            objective_mode_active=profile in {"work", "live", "strict"},
            live_production_claimed=False,
            raw_secret_echoed=message.strip() != normalized and message.strip() in assistant,
        )

    def session_payload(self, session_id: str) -> dict[str, object]:
        return self.store.export_session(session_id)


def _assistant_reply(message: str, provider_name: str) -> str:
    if _looks_like_objective(message):
        return (
            "Zeus is here. I can turn this into an objective contract, then "
            "separate authority, security exposure, evidence, and execution steps."
        )
    return (
        "Zeus is here. I can answer in chat mode using {0}; objective controls "
        "stay inactive until the task needs authority, tools, or external systems."
    ).format(provider_name)


def _looks_like_objective(message: str) -> bool:
    lowered = message.casefold()
    return any(
        marker in lowered
        for marker in (
            "implement",
            "ship",
            "deploy",
            "목표",
            "구현",
            "배포",
            "작업",
            "release",
        )
    )


def _title_from_message(message: str) -> str:
    words = message.split()
    if len(words) <= 6:
        return message[:80]
    return " ".join(words[:6])[:80]
