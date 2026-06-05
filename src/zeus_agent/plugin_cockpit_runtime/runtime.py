from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.plugin_runtime import validate_plugin_manifest

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


class PluginCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    plugin_count: int
    quarantined_plugin_count: int
    blocked_plugin_count: int
    selected_plugin: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    tool_registration_allowed: bool = False
    dependency_installed: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class PluginCockpitRuntime:
    def build(self, *, plugin_id: Optional[str] = None) -> PluginCockpitResult:
        plugins = _plugin_summaries()
        selected = _find_selected_plugin(plugins, plugin_id)
        blocked_reasons = _blocked_reasons(plugin_id=plugin_id, selected_plugin=selected)
        result = PluginCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            plugin_count=len(plugins),
            quarantined_plugin_count=sum(1 for item in plugins if item["validation_decision"] == "quarantined"),
            blocked_plugin_count=sum(1 for item in plugins if item["validation_decision"] == "blocked"),
            selected_plugin=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(plugin_id=plugin_id),
            tool_registration_allowed=False,
            dependency_installed=False,
            credential_material_accessed=False,
            network_opened=any(bool(item["network_opened"]) for item in plugins),
            handler_executed=any(bool(item["handler_executed"]) for item in plugins),
            external_delivery_opened=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _plugin_summaries() -> tuple[dict[str, JsonValue], ...]:
    return (
        _summary(
            plugin_id="safe-local",
            raw_manifest={
                "plugin_id": "safe-local",
                "name": "Safe Local Plugin",
                "version": "0.1.0",
                "entrypoint": "plugins/safe_local.py",
                "permissions": ["tool.read", "session.read"],
                "dependencies": ["pydantic"],
                "sha256": "b" * 64,
            },
        ),
        _summary(
            plugin_id="untrusted-network",
            raw_manifest={
                "plugin_id": "untrusted-network",
                "name": "Untrusted Network Plugin",
                "version": "0.1.0",
                "entrypoint": "plugins/untrusted_network.py",
                "permissions": ["tool.register", "live.network", "credential.write"],
                "dependencies": ["untrusted-package", "sk-" + "wave51-secret"],
                "sha256": "c" * 64,
            },
        ),
    )


def _summary(*, plugin_id: str, raw_manifest: dict[str, JsonValue]) -> dict[str, JsonValue]:
    validation = validate_plugin_manifest(raw_manifest)
    manifest = validation.manifest
    return {
        "plugin_id": plugin_id,
        "manifest_plugin_id": "" if manifest is None else manifest.plugin_id,
        "display_name": "" if manifest is None else manifest.name,
        "version": "" if manifest is None else manifest.version,
        "entrypoint": "" if manifest is None else manifest.entrypoint,
        "validation_decision": validation.decision,
        "reason": validation.reason,
        "blocked_reasons": list(validation.blocked_reasons),
        "quarantine_required": validation.decision == "quarantined",
        "tool_registration_allowed": validation.tool_registration_allowed,
        "dependency_installed": False,
        "credential_material_accessed": False,
        "network_opened": validation.network_opened,
        "handler_executed": validation.handler_executed,
        "live_production_claimed": validation.live_production_claimed,
    }


def _find_selected_plugin(
    plugins: tuple[dict[str, JsonValue], ...],
    plugin_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if plugin_id is None:
        return None
    for plugin in plugins:
        if plugin["plugin_id"] == plugin_id:
            return plugin
    return None


def _blocked_reasons(
    *,
    plugin_id: Optional[str],
    selected_plugin: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if plugin_id is not None and selected_plugin is None:
        return ("unknown_plugin",)
    return ()


def _recommended_next_commands(*, plugin_id: Optional[str]) -> tuple[str, ...]:
    if plugin_id is None:
        return (
            "zeus plugins --plugin-id safe-local --json",
            "zeus plugin-validate --manifest-json <json> --json",
            "zeus security --json",
        )
    return (
        "zeus plugin-validate --manifest-json <json> --json",
        "zeus security --json",
        "zeus live --json",
    )


def _no_secret_echo(result: PluginCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
