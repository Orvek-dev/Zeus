from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from zeus_agent.entry_runtime.live_provider import openai_chat_reply_through_trust_loop
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
    trust_receipt_id: str | None = None
    trust_evidence_record_id: str | None = None
    broker_evidence_bound: bool = False
    handler_executed: bool = False

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
            "trust_receipt_id": self.trust_receipt_id,
            "trust_evidence_record_id": self.trust_evidence_record_id,
            "broker_evidence_bound": self.broker_evidence_bound,
            "handler_executed": self.handler_executed,
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
        preference = ModelSettingsRuntime(self.home).show()
        selected_provider_id = provider_id if provider_id is not None else preference.provider_id
        provider = get_provider_profile(selected_provider_id)
        selected_model_id = (
            preference.model_id
            if preference.provider_id == provider.provider_id
            else provider.default_model
        )
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
        live_reply = (
            openai_chat_reply_through_trust_loop(
                home=self.home,
                message=normalized,
                model_id=selected_model_id,
            )
            if provider.provider_id == "openai"
            else None
        )
        assistant = (
            _assistant_reply(normalized, provider.display_name)
            if live_reply is None
            else live_reply.assistant_message
        )
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
            trust_receipt_id=None if live_reply is None else live_reply.trust_receipt_id,
            trust_evidence_record_id=None if live_reply is None else live_reply.trust_evidence_record_id,
            broker_evidence_bound=False if live_reply is None else live_reply.broker_evidence_bound,
            handler_executed=False if live_reply is None else live_reply.handler_executed,
        )

    def session_payload(self, session_id: str) -> dict[str, object]:
        return self.store.export_session(session_id)


def _assistant_reply(message: str, provider_name: str) -> str:
    call_response = _call_response(message)
    if call_response is not None:
        return call_response
    if _looks_like_objective(message):
        return (
            "Zeus is here. I can turn this into an objective contract, then "
            "separate authority, security exposure, evidence, and execution steps."
        )
    return (
        "Zeus is here. I can answer in chat mode using {0}; objective controls "
        "stay inactive until the task needs authority, tools, or external systems."
    ).format(provider_name)


def _call_response(message: str) -> str | None:
    normalized = message.strip().casefold()
    if normalized in {"제우스", "제우스야"}:
        return "네, 제우스입니다."
    if normalized in {"zeus", "zeus.", "hey zeus", "hello zeus"}:
        return "Zeus is here."
    return None


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
