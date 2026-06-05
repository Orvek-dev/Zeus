from __future__ import annotations

import json
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.mcp_runtime import curated_mcp_catalog_payload

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


class McpCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    catalog_entry_count: int
    beta_enabled_count: int
    unsafe_catalog_entry_count: int
    selected_server: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    resources_prompts_wrappers_enabled: bool
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class McpCockpitRuntime:
    def build(self, *, server_id: Optional[str] = None) -> McpCockpitResult:
        payload = curated_mcp_catalog_payload()
        selected = _find_selected_server(payload, server_id)
        blocked_reasons = _blocked_reasons(server_id=server_id, selected_server=selected)
        result = McpCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            catalog_entry_count=int(payload["catalog_entry_count"]),
            beta_enabled_count=int(payload["beta_enabled_count"]),
            unsafe_catalog_entry_count=int(payload["unsafe_catalog_entry_count"]),
            selected_server=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(server_id=server_id),
            resources_prompts_wrappers_enabled=bool(payload["resources_prompts_wrappers_enabled"]),
            credential_material_accessed=bool(payload["credential_material_accessed"]),
            network_opened=bool(payload["network_opened"]),
            handler_executed=bool(payload["handler_executed"]),
            live_production_claimed=bool(payload["live_production_claimed"]),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _find_selected_server(
    payload: dict[str, JsonValue],
    server_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if server_id is None:
        return None
    entries = payload["entries"]
    if not isinstance(entries, list):
        return None
    for item in entries:
        if not isinstance(item, dict) or item.get("server_id") != server_id:
            continue
        include_tools = item.get("include_tools")
        exclude_tools = item.get("exclude_tools")
        return {
            "server_id": str(item["server_id"]),
            "display_name": str(item["display_name"]),
            "transport": str(item["transport"]),
            "source_ref": str(item["source_ref"]),
            "source_pinned": bool(item["source_pinned"]),
            "state": str(item["state"]),
            "beta_enabled": bool(item["beta_enabled"]),
            "include_tool_count": len(include_tools) if isinstance(include_tools, list) else 0,
            "exclude_tool_count": len(exclude_tools) if isinstance(exclude_tools, list) else 0,
            "resources_enabled": bool(item["resources_enabled"]),
            "prompts_enabled": bool(item["prompts_enabled"]),
            "network_opened": bool(item["network_opened"]),
        }
    return None


def _blocked_reasons(
    *,
    server_id: Optional[str],
    selected_server: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if server_id is not None and selected_server is None:
        return ("unknown_mcp_server",)
    return ()


def _recommended_next_commands(*, server_id: Optional[str]) -> tuple[str, ...]:
    if server_id is None:
        return (
            "zeus mcp --server-id mcp.github --json",
            "zeus mcp-catalog --json",
            "zeus live --json",
        )
    return (
        "zeus mcp-catalog --json",
        "zeus mcp-discovery-normalize --server-id {0} --server-label <label> --tools-json <tools-list-json> --json".format(server_id),
        "zeus live --json",
    )


def _no_secret_echo(result: McpCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
