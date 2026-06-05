from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.model_runtime.provider_catalog import ProviderProfile, get_provider_profile
from zeus_agent.security.credentials import redact_secret_spans

ModelSettingsDecision = Literal["configured", "default", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ModelSettingsResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ModelSettingsDecision
    source: str
    provider_id: str
    model_id: str
    display_name: str
    api_mode: str
    runtime_kind: str
    local_first: bool
    requires_credential: bool
    requires_network_lease: bool
    network_host: Optional[str] = None
    credential_scope_label: Optional[str] = None
    config_path: str
    updated_at: Optional[str] = None
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    credential_material_accessed: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ModelSettingsRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config_path = home / "model-preference.json"

    def show(self) -> ModelSettingsResult:
        payload = _read_payload(self.config_path)
        provider_id = str(payload.get("provider_id", "fake")) if payload is not None else "fake"
        model_id = payload.get("model_id") if payload is not None else None
        source = "configured" if payload is not None else "default"
        try:
            profile = get_provider_profile(provider_id)
        except KeyError:
            profile = get_provider_profile("fake")
            return _result(
                config_path=self.config_path,
                decision="blocked",
                source=source,
                profile=profile,
                model_id=profile.default_model,
                blocked_reasons=("unknown_provider",),
            )
        return _result(
            config_path=self.config_path,
            decision="configured" if source == "configured" else "default",
            source=source,
            profile=profile,
            model_id=str(model_id) if model_id is not None else profile.default_model,
            updated_at=str(payload.get("updated_at")) if payload is not None and payload.get("updated_at") is not None else None,
        )

    def set(self, *, provider_ref: str, model_id: Optional[str] = None) -> ModelSettingsResult:
        redacted_ref = redact_secret_spans(provider_ref.strip())
        redacted_model = redact_secret_spans(model_id.strip()) if model_id is not None else None
        if redacted_ref == "" or (model_id is not None and redacted_model == ""):
            return _blocked_default(self.config_path, "empty_model_preference")
        if redacted_ref != provider_ref.strip() or (model_id is not None and redacted_model != model_id.strip()):
            return _blocked_default(self.config_path, "unsafe_credential_material_detected")

        provider_id, selected_model = _parse_provider_ref(redacted_ref, redacted_model)
        try:
            profile = get_provider_profile(provider_id)
        except KeyError:
            return _blocked_default(self.config_path, "unknown_provider")

        timestamp = datetime.now(timezone.utc).isoformat()
        self.home.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "provider_id": profile.provider_id,
                    "model_id": selected_model or profile.default_model,
                    "updated_at": timestamp,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return _result(
            config_path=self.config_path,
            decision="configured",
            source="configured",
            profile=profile,
            model_id=selected_model or profile.default_model,
            updated_at=timestamp,
        )


def _parse_provider_ref(provider_ref: str, model_id: Optional[str]) -> tuple[str, Optional[str]]:
    if "/" not in provider_ref:
        return provider_ref, model_id
    provider_id = provider_ref.split("/", 1)[0]
    return provider_id, model_id or provider_ref


def _read_payload(config_path: Path) -> Optional[dict[str, object]]:
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _blocked_default(config_path: Path, reason: str) -> ModelSettingsResult:
    profile = get_provider_profile("fake")
    return _result(
        config_path=config_path,
        decision="blocked",
        source="default",
        profile=profile,
        model_id=profile.default_model,
        blocked_reasons=(reason,),
    )


def _result(
    *,
    config_path: Path,
    decision: ModelSettingsDecision,
    source: str,
    profile: ProviderProfile,
    model_id: str,
    blocked_reasons: tuple[str, ...] = (),
    updated_at: Optional[str] = None,
) -> ModelSettingsResult:
    result = ModelSettingsResult(
        decision=decision,
        source=source,
        provider_id=profile.provider_id,
        model_id=model_id,
        display_name=profile.display_name,
        api_mode=profile.api_mode,
        runtime_kind=profile.runtime_kind,
        local_first=profile.local_first,
        requires_credential=profile.credential_scope is not None,
        requires_network_lease=profile.network_host is not None,
        network_host=profile.network_host,
        credential_scope_label=profile.credential_scope,
        config_path=str(config_path),
        updated_at=updated_at,
        blocked_reasons=blocked_reasons,
        network_opened=False,
        credential_material_accessed=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: ModelSettingsResult) -> bool:
    blob = result.model_dump_json().lower()
    return not any(
        marker in blob
        for marker in (
            "sk-wave",
            "ghp_",
            "github_pat_",
            "glpat-",
            "xoxb-",
            "xoxa-",
            "xoxp-",
            "token=sk",
            "password=",
            "secret=sk",
            "private_key",
            "-----begin",
        )
    )
