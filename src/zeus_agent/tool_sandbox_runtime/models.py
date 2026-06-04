from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

ToolSandboxAction = Literal["file_read", "file_write", "command_run"]
ToolSandboxDecision = Literal["allowed", "blocked", "error"]


@dataclass(frozen=True)
class ToolSandboxRequest:
    action: str
    root: Path
    path: Optional[str] = None
    content: Optional[str] = None
    command: Optional[str] = None
    backend: str = "local"
    mounts: tuple[str, ...] = ()
    egress_policy: str = "none"
    resource_profile: str = "bounded"
    budget_required: int = 1
    evidence_target: str = "mneme.wave18.tool_sandbox"


@dataclass(frozen=True)
class ToolSandboxResult:
    decision: ToolSandboxDecision
    reason: str
    action: str
    capability_id: str
    result: dict[str, object] | None = None
    evidence_count: int = 0
    broker_dispatch_used: bool = False
    evidence_record_created: bool = False
    handler_executed: bool = False
    network_opened: bool = False
    safe_env_used: bool = True
    no_secret_echo: bool = True


__all__ = [
    "ToolSandboxAction",
    "ToolSandboxDecision",
    "ToolSandboxRequest",
    "ToolSandboxResult",
]
