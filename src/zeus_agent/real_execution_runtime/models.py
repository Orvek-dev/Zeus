from __future__ import annotations

import json
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RealExecutionDecision = Literal["report", "blocked"]
RealExecutionScenario = Literal[
    "status",
    "local-execution-smoke",
    "browser-blocked-live",
    "blocked-network",
    "blocked-remote",
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


class RealExecutionContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RealExecutionDecision
    target_version: Literal["v1.4.0"]
    release_stage: Literal["browser_terminal_sandbox_execution"]
    objective_contract_id: Literal["zeus.v1.4.0.browser_terminal_sandbox_execution"]
    scenario: RealExecutionScenario
    blocked_reasons: tuple[str, ...] = ()
    real_execution_runtime_contract_available: bool = True
    terminal_facade_available: bool = True
    sandbox_dispatch_facade_available: bool = True
    tool_sandbox_executor_available: bool = True
    browser_dispatch_guard_available: bool = True
    local_terminal_smoke_ready: bool = False
    sandbox_command_smoke_ready: bool = False
    browser_live_guard_ready: bool = False
    network_block_ready: bool = False
    remote_sandbox_block_ready: bool = False
    real_execution_runtime_ready: bool = False
    production_ready: bool = False
    sandbox_terminal_contract: Optional[dict[str, JsonValue]] = None
    browser_guard: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_local_side_effects: bool = False
    handler_executed: bool = False
    local_process_executed: bool = False
    fixture_file_write_performed: bool = False
    file_write_executed: bool = False
    cleanup_performed: bool = False
    credential_material_accessed: bool = False
    external_delivery_opened: bool = False
    remote_execution_opened: bool = False
    raw_secret_returned: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RealExecutionContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = _RAW_SECRET_SPAN_PATTERN.search(serialized) is None
        return self.model_copy(update={"no_secret_echo": safe})
