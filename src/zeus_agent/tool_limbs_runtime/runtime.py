from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.tool_runtime import native_tool_catalog, native_tool_catalog_payload

ToolLimbsDecision = Literal["report", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)
_TARGET_VERSION: Final = "v0.7.0"


class ToolLimbsContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ToolLimbsDecision
    target_version: str
    objective_contract_id: str
    selected_tool_id: Optional[str] = None
    selected_tool: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    native_toolset_count: int
    native_tool_count: int
    native_tool_catalog_contract_available: bool = True
    mcp_tool_discovery_contract_available: bool = True
    api_connector_contract_available: bool = True
    connector_dry_run_only: bool = True
    include_exclude_policy_required: bool = True
    approval_lease_required: bool = True
    security_gate_required: bool = True
    evidence_capture_required: bool = True
    live_external_execution_enabled: bool = False
    raw_secret_marker_detected: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> ToolLimbsContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        return self.model_copy(
            update={"no_secret_echo": not any(marker in serialized for marker in _SECRET_MARKERS)},
        )


def build_tool_limbs_contract(*, tool_id: Optional[str] = None) -> ToolLimbsContract:
    candidate_tool_id = None if tool_id is None else tool_id.strip()
    raw_secret_marker_detected = _has_secret_marker(candidate_tool_id or "")
    selected_tool = _selected_tool(candidate_tool_id)
    selected_tool_id = _safe_selected_tool_id(candidate_tool_id, selected_tool)
    blocked_reasons = _blocked_reasons(
        candidate_tool_id=candidate_tool_id,
        selected_tool=selected_tool,
        raw_secret_marker_detected=raw_secret_marker_detected,
    )
    catalog_payload = native_tool_catalog_payload()
    result = ToolLimbsContract(
        decision="blocked" if blocked_reasons else "report",
        target_version=_TARGET_VERSION,
        objective_contract_id="zeus.v0.7.0.tool_limbs",
        selected_tool_id=selected_tool_id,
        selected_tool=selected_tool,
        blocked_reasons=blocked_reasons,
        native_toolset_count=int(catalog_payload["toolset_count"]),
        native_tool_count=int(catalog_payload["tool_count"]),
        raw_secret_marker_detected=raw_secret_marker_detected,
        live_production_claimed=bool(catalog_payload["live_production_claimed"]),
    )
    return result.with_secret_scan()


def _selected_tool(tool_id: Optional[str]) -> Optional[dict[str, JsonValue]]:
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
            }
    return None


def _safe_selected_tool_id(
    candidate_tool_id: Optional[str],
    selected_tool: Optional[dict[str, JsonValue]],
) -> Optional[str]:
    if candidate_tool_id is None:
        return None
    if selected_tool is not None:
        tool_id = selected_tool.get("tool_id")
        return tool_id if isinstance(tool_id, str) else "unknown"
    return "unknown"


def _blocked_reasons(
    *,
    candidate_tool_id: Optional[str],
    selected_tool: Optional[dict[str, JsonValue]],
    raw_secret_marker_detected: bool,
) -> tuple[str, ...]:
    reasons = []
    if candidate_tool_id is not None and selected_tool is None:
        reasons.append("unknown_tool")
    if raw_secret_marker_detected:
        reasons.append("raw_secret_marker_detected")
    return tuple(reasons)


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
