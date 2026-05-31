"""Local plugin, MCP, and tool-pack registry."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from zeus_agent.paths import registry_dir, ensure_private_dir
from zeus_agent.schemas.plugin import PluginManifest
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import read_json, write_private_json


def register_plugin(
    name: str,
    *,
    kind: Literal["local_plugin", "mcp_server", "tool_pack"] = "local_plugin",
    description: str = "",
    entrypoint: str = "",
    risk_level: Literal["low", "medium", "high"] = "medium",
    enabled: bool = False,
    home: Path | None = None,
) -> PluginManifest:
    manifest = PluginManifest(
        name=name,
        kind=kind,
        description=description,
        entrypoint=entrypoint,
        risk_level=risk_level,
        enabled=enabled and risk_level == "low",
        requires_approval=(risk_level != "low" or kind == "mcp_server"),
    )
    plugins = {plugin.plugin_id: plugin for plugin in list_plugins(home=home)}
    plugins[manifest.plugin_id] = manifest
    _write_plugins(list(plugins.values()), home=home)
    EventLog(home).append(
        new_trace_event(
            "plugins.registered",
            payload={"plugin_id": manifest.plugin_id, "name": name, "kind": kind, "enabled": manifest.enabled},
        )
    )
    return manifest


def list_plugins(*, home: Path | None = None) -> list[PluginManifest]:
    path = _plugins_path(home)
    if not path.exists():
        return []
    return [PluginManifest.model_validate(item) for item in read_json(path)]


def _write_plugins(plugins: list[PluginManifest], *, home: Path | None = None) -> Path:
    return write_private_json(_plugins_path(home), [plugin.model_dump(mode="json") for plugin in plugins])


def _plugins_path(home: Path | None = None) -> Path:
    path = registry_dir(home) / "plugins.json"
    ensure_private_dir(path.parent)
    return path

