"""Messaging and API gateway adapter registry.

Hermes has many live platform adapters. Zeus starts with a policy registry:
adapters can be declared and inspected, but outbound actions are disabled by
default and must be paired with approval before a future runner sends anything.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from zeus_agent.paths import registry_dir, ensure_private_dir
from zeus_agent.schemas.plugin import GatewayAdapterConfig
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import read_json, write_private_json


def register_gateway_adapter(
    platform: str,
    *,
    mode: Literal["read_only", "draft_only", "approved_send"] = "draft_only",
    secret_env_vars: list[str] | None = None,
    enabled: bool = False,
    home: Path | None = None,
) -> GatewayAdapterConfig:
    config = GatewayAdapterConfig(
        platform=platform,
        mode=mode,
        enabled=enabled and mode == "read_only",
        outbound_requires_approval=True,
        secret_env_vars=secret_env_vars or [],
    )
    adapters = list_gateway_adapters(home=home)
    adapters.append(config)
    _write_adapters(adapters, home=home)
    EventLog(home).append(
        new_trace_event(
            "gateway.adapter.registered",
            payload={"adapter_id": config.adapter_id, "platform": platform, "mode": mode, "enabled": config.enabled},
        )
    )
    return config


def list_gateway_adapters(*, home: Path | None = None) -> list[GatewayAdapterConfig]:
    path = _adapters_path(home)
    if not path.exists():
        return []
    return [GatewayAdapterConfig.model_validate(item) for item in read_json(path)]


def _write_adapters(adapters: list[GatewayAdapterConfig], *, home: Path | None = None) -> Path:
    return write_private_json(_adapters_path(home), [adapter.model_dump(mode="json") for adapter in adapters])


def _adapters_path(home: Path | None = None) -> Path:
    path = registry_dir(home) / "gateway_adapters.json"
    ensure_private_dir(path.parent)
    return path

