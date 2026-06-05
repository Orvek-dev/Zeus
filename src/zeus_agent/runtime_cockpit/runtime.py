from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.browser_runtime import BrowserDispatchFacade, BrowserDispatchRequest
from zeus_agent.sandbox_runtime import SandboxDispatchFacade, SandboxDispatchRequest
from zeus_agent.terminal_runtime import TerminalDispatchFacade, TerminalDispatchRequest

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_BACKEND_IDS: Final = ("browser", "terminal", "sandbox")
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


class RuntimeCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    backend_count: int
    planned_backend_count: int
    blocked_backend_count: int
    backends: tuple[dict[str, JsonValue], ...]
    selected_backend: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class RuntimeCockpitRuntime:
    def build(
        self,
        *,
        backend_id: Optional[str] = None,
        root: Optional[Path] = None,
    ) -> RuntimeCockpitResult:
        backends = _backend_summaries(root=root)
        selected = _find_selected_backend(backends, backend_id)
        blocked_reasons = _blocked_reasons(backend_id=backend_id, selected_backend=selected)
        result = RuntimeCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            backend_count=len(backends),
            planned_backend_count=sum(1 for item in backends if item["decision"] == "planned"),
            blocked_backend_count=sum(1 for item in backends if item["decision"] == "blocked"),
            backends=backends,
            selected_backend=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(backend_id=backend_id),
            credential_material_accessed=False,
            network_opened=any(bool(item["network_opened"]) for item in backends),
            handler_executed=any(bool(item["handler_executed"]) for item in backends),
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _backend_summaries(*, root: Optional[Path]) -> tuple[dict[str, JsonValue], ...]:
    return (
        _browser_summary(),
        _terminal_summary(root=root),
        _sandbox_summary(root=root),
    )


def _browser_summary() -> dict[str, JsonValue]:
    result = BrowserDispatchFacade().plan(
        BrowserDispatchRequest(
            target_url="http://127.0.0.1/",
            dry_run=True,
            evidence_target="mneme.wave47.runtime.browser",
        )
    )
    return {
        "backend_id": "browser",
        "display_name": "Browser",
        "decision": result.decision,
        "reason": result.reason,
        "capability_id": result.capability_id,
        "target_url": result.target_url,
        "dry_run": result.dry_run,
        "evidence_required": result.evidence_obligation.required,
        "cleanup_required": result.cleanup_obligation.required,
        "blocked_reasons": list(result.blocked_reasons),
        "handler_executed": result.handler_executed,
        "network_opened": result.network_opened,
    }


def _terminal_summary(*, root: Optional[Path]) -> dict[str, JsonValue]:
    result = TerminalDispatchFacade().plan(
        TerminalDispatchRequest(
            command="pwd",
            root=root,
            evidence_target="mneme.wave47.runtime.terminal",
        )
    )
    return {
        "backend_id": "terminal",
        "display_name": "Terminal",
        "decision": result.decision,
        "reason": result.reason,
        "capability_id": "terminal.run",
        "command": result.command,
        "argv": list(result.argv),
        "evidence_required": result.evidence_obligation.required,
        "cleanup_required": result.cleanup_obligation.required,
        "blocked_reasons": [],
        "handler_executed": result.handler_executed,
        "network_opened": result.network_opened,
    }


def _sandbox_summary(*, root: Optional[Path]) -> dict[str, JsonValue]:
    result = SandboxDispatchFacade().plan(
        SandboxDispatchRequest(
            root=root,
            commands=("pwd",),
            cleanup_required=True,
            cleanup_plan="remove temporary sandbox workspace after evidence capture",
            evidence_target="mneme.wave47.runtime.sandbox",
        )
    )
    return {
        "backend_id": "sandbox",
        "display_name": "Sandbox",
        "decision": result.decision,
        "reason": result.reason,
        "capability_id": "sandbox.local.plan",
        "backend": result.backend_requirement.value,
        "egress_policy": result.egress_requirement.value,
        "resource_profile": result.resource_requirement.value,
        "command_count": len(result.command_plans),
        "evidence_required": result.evidence_obligation.required,
        "cleanup_required": result.cleanup_obligation.required,
        "blocked_reasons": list(result.blocked_reasons),
        "handler_executed": result.handler_executed,
        "network_opened": result.network_opened,
    }


def _find_selected_backend(
    backends: tuple[dict[str, JsonValue], ...],
    backend_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if backend_id is None:
        return None
    for backend in backends:
        if backend["backend_id"] == backend_id:
            return backend
    return None


def _blocked_reasons(
    *,
    backend_id: Optional[str],
    selected_backend: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if backend_id is not None and selected_backend is None:
        return ("unknown_runtime_backend",)
    return ()


def _recommended_next_commands(*, backend_id: Optional[str]) -> tuple[str, ...]:
    if backend_id is None:
        return (
            "zeus runtime --backend terminal --json",
            "zeus terminal-plan --command pwd --json",
            "zeus sandbox-plan --command pwd --json",
        )
    return (
        "zeus browser-plan --target-url http://127.0.0.1/ --json",
        "zeus terminal-plan --command pwd --json",
        "zeus sandbox-plan --command pwd --json",
    )


def _no_secret_echo(result: RuntimeCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
