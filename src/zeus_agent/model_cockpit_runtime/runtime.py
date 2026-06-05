from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.model_runtime import provider_catalog_payload

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


class ModelCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    provider_profile_count: int
    api_modes: tuple[str, ...]
    local_first_count: int
    tool_calling_count: int
    selected_provider: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ModelCockpitRuntime:
    def build(self, *, provider_id: Optional[str] = None) -> ModelCockpitResult:
        payload = provider_catalog_payload()
        selected = _find_selected_provider(payload, provider_id)
        blocked_reasons = _blocked_reasons(provider_id=provider_id, selected_provider=selected)
        result = ModelCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            provider_profile_count=int(payload["provider_profile_count"]),
            api_modes=tuple(str(mode) for mode in payload["api_modes"]),
            local_first_count=int(payload["local_first_count"]),
            tool_calling_count=int(payload["tool_calling_count"]),
            selected_provider=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(provider_id=provider_id),
            live_production_claimed=bool(payload["live_production_claimed"]),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _find_selected_provider(
    payload: dict[str, JsonValue],
    provider_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if provider_id is None:
        return None
    profiles = payload["profiles"]
    if not isinstance(profiles, list):
        return None
    for item in profiles:
        if not isinstance(item, dict) or item.get("provider_id") != provider_id:
            continue
        credential_scope = item.get("credential_scope")
        network_host = item.get("network_host")
        return {
            "provider_id": str(item["provider_id"]),
            "display_name": str(item["display_name"]),
            "api_mode": str(item["api_mode"]),
            "default_model": str(item["default_model"]),
            "runtime_kind": str(item["runtime_kind"]),
            "network_host": str(network_host) if network_host is not None else None,
            "credential_scope_label": str(credential_scope) if credential_scope is not None else None,
            "local_first": bool(item["local_first"]),
            "tool_calling": bool(item["tool_calling"]),
            "streaming": bool(item["streaming"]),
            "structured_output": bool(item["structured_output"]),
            "vision": bool(item["vision"]),
            "embeddings": bool(item["embeddings"]),
            "live_beta": bool(item["live_beta"]),
            "requires_credential": credential_scope is not None,
            "requires_network_lease": network_host is not None,
        }
    return None


def _blocked_reasons(
    *,
    provider_id: Optional[str],
    selected_provider: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if provider_id is not None and selected_provider is None:
        return ("unknown_provider",)
    return ()


def _recommended_next_commands(*, provider_id: Optional[str]) -> tuple[str, ...]:
    if provider_id is None:
        return (
            "zeus model --provider-id openai --json",
            "zeus providers --json",
            "zeus setup --provider",
            "zeus live --json",
        )
    return (
        "zeus provider-fallback-check --primary-provider-id local-llm --fallback-provider-id {0} --json".format(provider_id),
        "zeus setup --provider",
        "zeus live --json",
    )


def _no_secret_echo(result: ModelCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
