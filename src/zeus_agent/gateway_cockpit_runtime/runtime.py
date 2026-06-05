from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.gateway_runtime import gateway_adapter_catalog_payload

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


class GatewayCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    adapter_count: int
    fake_smoke_adapter_count: int
    selected_adapter: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    auth_required: bool
    pairing_required: bool
    delivery_target_allowlist_required: bool
    external_delivery_opened: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class GatewayCockpitRuntime:
    def build(self, *, adapter_id: Optional[str] = None) -> GatewayCockpitResult:
        payload = gateway_adapter_catalog_payload()
        selected = _find_selected_adapter(payload, adapter_id)
        blocked_reasons = _blocked_reasons(adapter_id=adapter_id, selected_adapter=selected)
        result = GatewayCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            adapter_count=int(payload["adapter_count"]),
            fake_smoke_adapter_count=int(payload["fake_smoke_adapter_count"]),
            selected_adapter=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(adapter_id=adapter_id),
            auth_required=bool(payload["auth_required"]),
            pairing_required=bool(payload["pairing_required"]),
            delivery_target_allowlist_required=bool(payload["delivery_target_allowlist_required"]),
            external_delivery_opened=bool(payload["external_delivery_opened"]),
            network_opened=bool(payload["network_opened"]),
            live_production_claimed=bool(payload["live_production_claimed"]),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _find_selected_adapter(
    payload: dict[str, JsonValue],
    adapter_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if adapter_id is None:
        return None
    adapters = payload["adapters"]
    if not isinstance(adapters, list):
        return None
    for item in adapters:
        if not isinstance(item, dict) or item.get("adapter_id") != adapter_id:
            continue
        return {
            "adapter_id": str(item["adapter_id"]),
            "display_name": str(item["display_name"]),
            "state": str(item["state"]),
            "fake_smoke_enabled": bool(item["fake_smoke_enabled"]),
            "auth_required": bool(item["auth_required"]),
            "pairing_required": bool(item["pairing_required"]),
            "delivery_target_allowlist_required": bool(item["delivery_target_allowlist_required"]),
            "live_delivery_supported": bool(item["live_delivery_supported"]),
            "external_delivery_opened": bool(item["external_delivery_opened"]),
            "network_opened": bool(item["network_opened"]),
        }
    return None


def _blocked_reasons(
    *,
    adapter_id: Optional[str],
    selected_adapter: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if adapter_id is not None and selected_adapter is None:
        return ("unknown_gateway_adapter",)
    return ()


def _recommended_next_commands(*, adapter_id: Optional[str]) -> tuple[str, ...]:
    if adapter_id is None:
        return (
            "zeus gateway --adapter-id slack --json",
            "zeus gateway-adapters --json",
            "zeus live --json",
        )
    return (
        "zeus live-optin-smoke --scenario happy --json",
        "zeus gateway-adapters --json",
        "zeus live --json",
    )


def _no_secret_echo(result: GatewayCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
