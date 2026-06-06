from __future__ import annotations

import json
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RealProductPlatformDecision = Literal["report", "blocked"]
RealProductPlatformScenario = Literal[
    "status",
    "persona-smoke",
    "platform-cockpit-smoke",
    "live-status-smoke",
    "operator-command-map",
    "public-boundary",
]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
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


class RealProductPlatformContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RealProductPlatformDecision
    target_version: Literal["v1.7.0"]
    release_stage: Literal["product_ux_platform_status"]
    objective_contract_id: Literal["zeus.v1.7.0.product_ux_platform_status"]
    scenario: RealProductPlatformScenario
    blocked_reasons: tuple[str, ...] = ()
    real_product_platform_contract_available: bool = True
    persona_surface_available: bool = True
    platform_cockpit_available: bool = True
    live_status_surface_available: bool = True
    model_status_surface_available: bool = True
    mcp_status_surface_available: bool = True
    runtime_status_surface_available: bool = True
    operator_command_map_available: bool = True
    public_boundary_report_available: bool = True
    product_platform_ready: bool = False
    persona_surface_ready: bool = False
    platform_status_ready: bool = False
    live_status_ready: bool = False
    operator_command_map_ready: bool = False
    public_boundary_ready: bool = False
    production_ready: bool = False
    zeus_call_response: Literal["Zeus is here."] = "Zeus is here."
    zeus_korean_call_response: Literal["네, Zeus입니다."] = "네, Zeus입니다."
    persona_contract: Optional[dict[str, JsonValue]] = None
    platform_contract: Optional[dict[str, JsonValue]] = None
    live_cockpit_contract: Optional[dict[str, JsonValue]] = None
    model_cockpit_contract: Optional[dict[str, JsonValue]] = None
    mcp_cockpit_contract: Optional[dict[str, JsonValue]] = None
    runtime_cockpit_contract: Optional[dict[str, JsonValue]] = None
    status_surface_count: int = 0
    blocked_surface_count: int = 0
    operator_command_count: int = 0
    operator_commands: tuple[str, ...] = ()
    chat_turn_started: bool = False
    api_server_started: bool = False
    gateway_daemon_started: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    authority_widened: bool = False
    active_rule_written: bool = False
    raw_secret_marker_detected: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    cleanup_performed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RealProductPlatformContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = _RAW_SECRET_SPAN_PATTERN.search(serialized) is None
        return self.model_copy(update={"no_secret_echo": safe})
