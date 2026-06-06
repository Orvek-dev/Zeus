from __future__ import annotations

import json
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RealMcpDecision = Literal["report", "blocked"]
RealMcpScenario = Literal[
    "status",
    "catalog",
    "setup-dry-run",
    "list",
    "inspect",
    "test-loopback",
    "login-dry-run",
    "blocked-resource-prompt",
    "blocked-unpinned",
    "blocked-prompt-injection",
]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_UNSAFE_TEXT_MARKERS: Final[tuple[str, ...]] = (
    "reveal secret",
    "ignore previous instructions",
)
_RAW_SECRET_SPAN_PATTERN: Final = re.compile(
    r"sk-[a-z0-9][a-z0-9._-]*"
    r"|ghp_[a-z0-9_]+"
    r"|github_pat_[a-z0-9_]+"
    r"|glpat-[a-z0-9_-]+"
    r"|xox[abp]-[a-z0-9-]+"
    r"|bearer\s+[a-z0-9._~+/=-]+"
    r"|(api[ _-]?key|private[ _-]?key|token|password|secret)\s*[=:]\s*[^\s\"'}]+"
    r"|(aws_access_key_id|aws_secret_access_key|aws_session_token)\s*[=:]\s*[^\s\"'}]+",
)


class RealMcpContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RealMcpDecision
    target_version: Literal["v1.2.0"]
    release_stage: Literal["real_mcp_runtime"]
    objective_contract_id: Literal["zeus.v1.2.0.real_mcp_runtime"]
    scenario: RealMcpScenario
    blocked_reasons: tuple[str, ...] = ()
    real_mcp_runtime_contract_available: bool = True
    mcp_catalog_available: bool = True
    mcp_catalog_runtime_available: bool = True
    mcp_setup_dry_run_available: bool = True
    mcp_add_server_dry_run_available: bool = True
    mcp_list_server_available: bool = True
    mcp_inspect_manifest_available: bool = True
    mcp_governed_smoke_available: bool = True
    mcp_login_dry_run_available: bool = True
    mcp_include_exclude_policy_available: bool = True
    mcp_resource_prompt_policy_available: bool = True
    real_mcp_runtime_ready: bool = False
    production_ready: bool = False
    catalog_entry_count: int = 0
    beta_enabled_count: int = 0
    selected_server_id: Optional[str] = None
    selected_transport: Optional[str] = None
    selected_source_ref: Optional[str] = None
    include_tools: tuple[str, ...] = ()
    exclude_tools: tuple[str, ...] = ()
    compiled_tool_count: int = 0
    compiled_tool_names: tuple[str, ...] = ()
    catalog: Optional[dict[str, JsonValue]] = None
    setup_plan: Optional[dict[str, JsonValue]] = None
    list_snapshot: Optional[dict[str, JsonValue]] = None
    inspect_result: Optional[dict[str, JsonValue]] = None
    test_result: Optional[dict[str, JsonValue]] = None
    login_plan: Optional[dict[str, JsonValue]] = None
    resources_enabled: bool = False
    prompts_enabled: bool = False
    server_started: bool = False
    subprocess_started: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RealMcpContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = _RAW_SECRET_SPAN_PATTERN.search(serialized) is None and not any(
            marker in serialized for marker in _UNSAFE_TEXT_MARKERS
        )
        return self.model_copy(update={"no_secret_echo": safe})
