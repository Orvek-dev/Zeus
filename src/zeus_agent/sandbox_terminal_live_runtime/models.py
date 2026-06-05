from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

SandboxTerminalLiveDecision = Literal["report", "blocked"]
SandboxTerminalLiveScenario = Literal["status", "local-smoke", "blocked-network", "blocked-remote"]

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


class SandboxTerminalLiveContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SandboxTerminalLiveDecision
    target_version: str
    release_stage: Literal["sandbox_terminal_live"]
    objective_contract_id: str
    scenario: SandboxTerminalLiveScenario
    blocked_reasons: tuple[str, ...] = ()
    sandbox_terminal_live_contract_available: bool = True
    terminal_facade_available: bool = True
    sandbox_dispatch_facade_available: bool = True
    tool_sandbox_executor_available: bool = True
    browser_dispatch_guard_available: bool = True
    local_terminal_smoke_available: bool = True
    local_sandbox_execution_ready: bool = False
    remote_sandbox_available: bool = False
    docker_backend_available: bool = False
    ssh_backend_available: bool = False
    browser_live_navigation_available: bool = False
    production_ready: bool = False
    sandbox_smoke: Optional[dict[str, JsonValue]] = None
    terminal_plan: Optional[dict[str, JsonValue]] = None
    sandbox_plan: Optional[dict[str, JsonValue]] = None
    browser_guard: Optional[dict[str, JsonValue]] = None
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    controlled_local_side_effects: bool = False
    handler_executed: bool = False
    local_process_executed: bool = False
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

    def with_secret_scan(self) -> SandboxTerminalLiveContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        return self.model_copy(update={"no_secret_echo": not any(marker in serialized for marker in _SECRET_MARKERS)})
