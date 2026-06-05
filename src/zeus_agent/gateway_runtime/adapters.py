from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from zeus_agent.security.credentials import redact_secret_spans

GatewayAdapterState = Literal["dry_run", "planned_wave"]
_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, strict=True)


class GatewayAdapterSpec(BaseModel):
    model_config = _MODEL_CONFIG

    adapter_id: str
    display_name: str
    state: GatewayAdapterState
    fake_smoke_enabled: bool = False
    auth_required: bool = True
    pairing_required: bool = True
    delivery_target_allowlist_required: bool = True
    live_delivery_supported: bool = False
    external_delivery_opened: bool = False
    network_opened: bool = False


def default_gateway_adapter_specs() -> tuple[GatewayAdapterSpec, ...]:
    raw = (
        ("telegram", "Telegram"),
        ("discord", "Discord"),
        ("slack", "Slack"),
        ("webhook", "Webhook"),
        ("email", "Email"),
        ("matrix", "Matrix"),
        ("teams", "Microsoft Teams"),
        ("signal", "Signal"),
        ("sms", "SMS"),
        ("mattermost", "Mattermost"),
        ("mastodon", "Mastodon"),
        ("bluesky", "Bluesky"),
    )
    return tuple(
        GatewayAdapterSpec(
            adapter_id=adapter_id,
            display_name=display_name,
            state="dry_run" if index < 3 else "planned_wave",
            fake_smoke_enabled=index < 3,
        )
        for index, (adapter_id, display_name) in enumerate(raw)
    )


def gateway_adapter_catalog_payload() -> dict[str, object]:
    adapters = default_gateway_adapter_specs()
    fake_smoke = [adapter for adapter in adapters if adapter.fake_smoke_enabled]
    return {
        "adapter_count": len(adapters),
        "fake_smoke_adapter_count": len(fake_smoke),
        "adapters": [adapter.model_dump(mode="json") for adapter in adapters],
        "auth_required": True,
        "pairing_required": True,
        "delivery_target_allowlist_required": True,
        "external_delivery_opened": False,
        "network_opened": False,
        "live_production_claimed": False,
    }


def plan_gateway_adapter_delivery(
    *,
    adapter_id: str,
    target: str,
    allowlisted_targets: tuple[str, ...] = (),
    auth_receipt_id: Optional[str] = None,
    pairing_receipt_id: Optional[str] = None,
) -> dict[str, object]:
    safe_target = redact_secret_spans(target)
    safe_adapter_id = redact_secret_spans(adapter_id)
    known_ids = {adapter.adapter_id for adapter in default_gateway_adapter_specs()}
    blocked_reasons: list[str] = []
    if safe_adapter_id not in known_ids:
        blocked_reasons.append("unknown_gateway_adapter")
    if auth_receipt_id is None:
        blocked_reasons.append("gateway_auth_required")
    if pairing_receipt_id is None:
        blocked_reasons.append("gateway_pairing_required")
    if safe_target not in allowlisted_targets:
        blocked_reasons.append("delivery_target_not_allowlisted")
    payload = {
        "decision": "blocked" if blocked_reasons else "planned",
        "adapter_id": safe_adapter_id,
        "target": safe_target,
        "blocked_reasons": tuple(dict.fromkeys(blocked_reasons)),
        "external_delivery_opened": False,
        "network_opened": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }
    payload["no_secret_echo"] = _no_secret_echo(payload)
    return payload


def _no_secret_echo(payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    raw_markers = ("sk-wave", "token=sk", "ghp_", "github_pat_", "bearer ")
    return not any(marker in serialized for marker in raw_markers)


__all__ = [
    "GatewayAdapterSpec",
    "default_gateway_adapter_specs",
    "gateway_adapter_catalog_payload",
    "plan_gateway_adapter_delivery",
]
