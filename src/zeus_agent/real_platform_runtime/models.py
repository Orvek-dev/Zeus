from __future__ import annotations

import json
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

RealPlatformDecision = Literal["report", "blocked"]
RealPlatformScenario = Literal[
    "status",
    "api-dry-run",
    "gateway-loopback-smoke",
    "gateway-blocked-external",
    "session-secret-boundary",
    "batch-acp-smoke",
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


class RealPlatformContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: RealPlatformDecision
    target_version: Literal["v1.3.0"]
    release_stage: Literal["gateway_api_session_platform"]
    objective_contract_id: Literal["zeus.v1.3.0.gateway_api_session_platform"]
    scenario: RealPlatformScenario
    blocked_reasons: tuple[str, ...] = ()
    real_platform_runtime_contract_available: bool = True
    api_runtime_available: bool = True
    gateway_runtime_available: bool = True
    session_store_available: bool = True
    acp_adapter_available: bool = True
    batch_runner_available: bool = True
    python_library_available: bool = True
    api_dry_run_ready: bool = False
    gateway_loopback_ready: bool = False
    session_store_ready: bool = False
    session_export_ready: bool = False
    batch_runner_ready: bool = False
    acp_adapter_ready: bool = False
    real_platform_runtime_ready: bool = False
    production_ready: bool = False
    api_routes: tuple[str, ...] = ()
    gateway_decision: Optional[str] = None
    gateway_reason: Optional[str] = None
    gateway_session_count: int = 0
    gateway_audit_records: int = 0
    idempotency_replay_stable: bool = False
    session_message_count: int = 0
    batch_compiled_count: int = 0
    batch_blocked_count: int = 0
    acp_method: Optional[str] = None
    server_started: bool = False
    handler_executed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    cleanup_performed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RealPlatformContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = _RAW_SECRET_SPAN_PATTERN.search(serialized) is None
        return self.model_copy(update={"no_secret_echo": safe})
