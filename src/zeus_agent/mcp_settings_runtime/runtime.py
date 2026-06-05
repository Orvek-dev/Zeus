from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.mcp_runtime import McpCatalogEntry, default_mcp_catalog_entries
from zeus_agent.security.credentials import redact_secret_spans

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_UNSAFE_REF_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous",
    "ignore system",
    "override system",
    "reveal prompt",
    "jailbreak",
)


class McpSettingsResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    configured_server_count: int
    configured_servers: tuple[dict[str, JsonValue], ...]
    selected_server: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    config_path: str
    server_started: bool = False
    resources_prompts_wrappers_enabled: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class McpSettingsRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config_path = home / "mcp-config.json"

    def add(self, *, server_ref: str) -> McpSettingsResult:
        redacted_ref = redact_secret_spans(server_ref.strip())
        if redacted_ref != server_ref.strip():
            return self._blocked("unsafe_credential_material_detected")
        if redacted_ref == "":
            return self._blocked("empty_mcp_ref")
        if _unsafe_ref(redacted_ref):
            return self._blocked("unsafe_mcp_ref")

        entry = _find_catalog_entry(redacted_ref)
        if entry is None:
            return self._blocked("unknown_mcp_server")

        configured = [item for item in self._configured_servers() if item["server_id"] != entry.server_id]
        selected = _server_payload(entry, updated_at=datetime.now(timezone.utc).isoformat())
        configured.append(selected)
        self.home.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps({"servers": configured}, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return _result(
            config_path=self.config_path,
            decision="configured",
            configured_servers=tuple(configured),
            selected_server=selected,
        )

    def list(self) -> McpSettingsResult:
        configured = tuple(self._configured_servers())
        return _result(
            config_path=self.config_path,
            decision="report",
            configured_servers=configured,
        )

    def _configured_servers(self) -> list[dict[str, JsonValue]]:
        if not self.config_path.exists():
            return []
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(payload, dict):
            return []
        servers = payload.get("servers", [])
        if not isinstance(servers, list):
            return []
        result: list[dict[str, JsonValue]] = []
        for item in servers:
            if isinstance(item, dict) and isinstance(item.get("server_id"), str):
                result.append(_normalize_configured_server(item))
        return result

    def _blocked(self, reason: str) -> McpSettingsResult:
        return _result(
            config_path=self.config_path,
            decision="blocked",
            configured_servers=tuple(self._configured_servers()),
            blocked_reasons=(reason,),
        )


def _find_catalog_entry(server_ref: str) -> Optional[McpCatalogEntry]:
    normalized = server_ref.strip().casefold()
    for entry in default_mcp_catalog_entries():
        aliases = {
            entry.server_id.casefold(),
            entry.server_id.removeprefix("mcp.").casefold(),
            entry.display_name.casefold(),
            entry.toolset_hint.casefold(),
        }
        if normalized in aliases:
            return entry
    return None


def _unsafe_ref(server_ref: str) -> bool:
    lowered = server_ref.casefold()
    return any(marker in lowered for marker in _UNSAFE_REF_MARKERS)


def _server_payload(entry: McpCatalogEntry, *, updated_at: str) -> dict[str, JsonValue]:
    return {
        "server_id": entry.server_id,
        "display_name": entry.display_name,
        "transport": entry.transport,
        "source_ref": entry.source_ref,
        "source_pinned": entry.source_pinned,
        "state": "quarantined",
        "catalog_state": entry.state,
        "beta_enabled": entry.beta_enabled,
        "include_tools": list(entry.include_tools),
        "exclude_tools": list(entry.exclude_tools),
        "requires_credential": entry.requires_credential,
        "credential_scope": entry.credential_scope,
        "resources_enabled": False,
        "prompts_enabled": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "updated_at": updated_at,
    }


def _normalize_configured_server(item: dict[str, object]) -> dict[str, JsonValue]:
    include_tools = item.get("include_tools", [])
    exclude_tools = item.get("exclude_tools", [])
    return {
        "server_id": str(item["server_id"]),
        "display_name": str(item.get("display_name", item["server_id"])),
        "transport": str(item.get("transport", "stdio")),
        "source_ref": str(item.get("source_ref", "")),
        "source_pinned": bool(item.get("source_pinned", False)),
        "state": str(item.get("state", "quarantined")),
        "catalog_state": str(item.get("catalog_state", "planned_wave")),
        "beta_enabled": bool(item.get("beta_enabled", False)),
        "include_tools": [str(value) for value in include_tools] if isinstance(include_tools, list) else [],
        "exclude_tools": [str(value) for value in exclude_tools] if isinstance(exclude_tools, list) else [],
        "requires_credential": bool(item.get("requires_credential", False)),
        "credential_scope": str(item["credential_scope"]) if isinstance(item.get("credential_scope"), str) else None,
        "resources_enabled": False,
        "prompts_enabled": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "updated_at": str(item.get("updated_at", "")),
    }


def _result(
    *,
    config_path: Path,
    decision: str,
    configured_servers: tuple[dict[str, JsonValue], ...],
    selected_server: Optional[dict[str, JsonValue]] = None,
    blocked_reasons: tuple[str, ...] = (),
) -> McpSettingsResult:
    result = McpSettingsResult(
        decision=decision,
        configured_server_count=len(configured_servers),
        configured_servers=configured_servers,
        selected_server=selected_server,
        blocked_reasons=blocked_reasons,
        config_path=str(config_path),
        server_started=False,
        resources_prompts_wrappers_enabled=False,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: McpSettingsResult) -> bool:
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
