from __future__ import annotations

import json
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.tool_runtime import native_tool_catalog, native_tool_catalog_payload

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


class ToolCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    toolset_count: int
    tool_count: int
    selected_tool: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ToolCockpitRuntime:
    def build(self, *, tool_id: Optional[str] = None) -> ToolCockpitResult:
        payload = native_tool_catalog_payload()
        selected = _find_selected_tool(tool_id)
        blocked_reasons = _blocked_reasons(tool_id=tool_id, selected_tool=selected)
        result = ToolCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            toolset_count=int(payload["toolset_count"]),
            tool_count=int(payload["tool_count"]),
            selected_tool=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(tool_id=tool_id),
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            live_production_claimed=bool(payload["live_production_claimed"]),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _find_selected_tool(tool_id: Optional[str]) -> Optional[dict[str, JsonValue]]:
    if tool_id is None:
        return None
    for toolset in native_tool_catalog():
        for tool in toolset.tools:
            if tool.name != tool_id:
                continue
            return {
                "tool_id": tool.name,
                "toolset_id": toolset.toolset_id,
                "display_name": toolset.display_name,
                "description": tool.description,
                "capability_id": tool.capability_id,
                "source": tool.source,
                "budget_required": tool.budget_required,
                "credential_scope_required": tool.credential_scope is not None,
                "network_host_required": tool.network_host is not None,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
                "network_opened": False,
                "handler_executed": False,
            }
    return None


def _blocked_reasons(
    *,
    tool_id: Optional[str],
    selected_tool: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if tool_id is not None and selected_tool is None:
        return ("unknown_tool",)
    return ()


def _recommended_next_commands(*, tool_id: Optional[str]) -> tuple[str, ...]:
    if tool_id is None:
        return (
            "zeus tools --tool-id files.read --json",
            "zeus tool-catalog --json",
            "zeus live --json",
        )
    return (
        "zeus tool-catalog --json",
        "zeus terminal-plan --command <command> --json",
        "zeus live --json",
    )


def _no_secret_echo(result: ToolCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
