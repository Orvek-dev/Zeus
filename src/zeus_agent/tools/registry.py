"""Hermes-style self-registering tool broker for Zeus.

Tools are normal Python callables, but every call receives a ToolContext and is
expected to produce evidence or an explicit blocked result. This keeps the
surface extensible without bypassing Zeus' approval and Mneme layers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any, Literal

from zeus_agent.core.mneme import diff_gate, record_command_evidence, record_evidence
from zeus_agent.runtime.sandbox import SandboxPolicyError, SandboxRuntime
from zeus_agent.schemas.agent import ToolCallRequest, ToolCallResult
from zeus_agent.storage.state import StateStore


ToolRisk = Literal["low", "medium", "high"]
ToolFn = Callable[["ToolContext", dict[str, Any]], ToolCallResult]


@dataclass(frozen=True)
class ToolContext:
    run_id: str
    home: Path | None = None
    session_id: str | None = None
    approved: bool = False


@dataclass(frozen=True)
class ToolEntry:
    name: str
    description: str
    risk_level: ToolRisk
    requires_approval: bool
    handler: ToolFn = field(repr=False)


class ToolRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        description: str,
        *,
        risk_level: ToolRisk = "medium",
        requires_approval: bool | None = None,
    ) -> Callable[[ToolFn], ToolFn]:
        def decorator(fn: ToolFn) -> ToolFn:
            entry = ToolEntry(
                name=name,
                description=description,
                risk_level=risk_level,
                requires_approval=(risk_level != "low") if requires_approval is None else requires_approval,
                handler=fn,
            )
            with self._lock:
                self._entries[name] = entry
            return fn

        return decorator

    def list(self) -> list[ToolEntry]:
        with self._lock:
            return sorted(self._entries.values(), key=lambda entry: entry.name)

    def get(self, name: str) -> ToolEntry:
        with self._lock:
            if name not in self._entries:
                raise KeyError(f"unknown Zeus tool: {name}")
            return self._entries[name]

    def execute(self, context: ToolContext, request: ToolCallRequest) -> ToolCallResult:
        try:
            entry = self.get(request.name)
        except KeyError as exc:
            return ToolCallResult(
                call_id=request.call_id,
                name=request.name,
                status="blocked",
                summary=str(exc),
            )
        if entry.requires_approval and not context.approved:
            return ToolCallResult(
                call_id=request.call_id,
                name=request.name,
                status="blocked",
                summary=f"{request.name} requires an approved GoalContract.",
            )
        arguments = dict(request.arguments)
        arguments.setdefault("call_id", request.call_id)
        return entry.handler(context, arguments)


_DEFAULT_REGISTRY = ToolRegistry()


def default_tool_registry() -> ToolRegistry:
    return _DEFAULT_REGISTRY


@_DEFAULT_REGISTRY.register(
    "zeus.record_note",
    "Record a non-mutating note as Mneme evidence.",
    risk_level="low",
    requires_approval=False,
)
def _record_note(context: ToolContext, arguments: dict[str, Any]) -> ToolCallResult:
    summary = str(arguments.get("summary") or "Agent note.")
    evidence = record_evidence(
        context.run_id,
        "note",
        summary,
        passed=bool(arguments.get("passed", True)),
        payload={"note": arguments.get("note", summary)},
        home=context.home,
    )
    return ToolCallResult(
        call_id=str(arguments.get("call_id") or "direct"),
        name="zeus.record_note",
        status="completed",
        summary=summary,
        evidence_ids=[evidence.evidence_id],
    )


@_DEFAULT_REGISTRY.register(
    "zeus.checkpoint",
    "Capture a restorable workspace checkpoint.",
    risk_level="medium",
)
def _checkpoint(context: ToolContext, arguments: dict[str, Any]) -> ToolCallResult:
    checkpoint = SandboxRuntime(context.home).create_checkpoint(context.run_id)
    evidence = record_evidence(
        context.run_id,
        "checkpoint",
        f"Checkpoint {checkpoint.checkpoint_id} captured {checkpoint.file_count} files.",
        passed=True,
        artifact_paths=[checkpoint.content_snapshot_path] if checkpoint.content_snapshot_path else [],
        payload=checkpoint.model_dump(mode="json"),
        home=context.home,
    )
    return ToolCallResult(
        call_id=str(arguments.get("call_id") or "direct"),
        name="zeus.checkpoint",
        status="completed",
        summary=f"Captured checkpoint {checkpoint.checkpoint_id}.",
        evidence_ids=[evidence.evidence_id],
        artifact_paths=[checkpoint.content_snapshot_path] if checkpoint.content_snapshot_path else [],
        result={"checkpoint_id": checkpoint.checkpoint_id, "restorable": checkpoint.restorable},
    )


@_DEFAULT_REGISTRY.register(
    "zeus.sandbox_command",
    "Run a command through the approval-gated local sandbox.",
    risk_level="high",
)
def _sandbox_command(context: ToolContext, arguments: dict[str, Any]) -> ToolCallResult:
    argv = arguments.get("argv")
    if not isinstance(argv, list) or not all(isinstance(part, str) for part in argv):
        return ToolCallResult(
            call_id=str(arguments.get("call_id") or "direct"),
            name="zeus.sandbox_command",
            status="blocked",
            summary="argv must be a list of strings.",
        )
    try:
        result = SandboxRuntime(context.home).run_command(
            context.run_id,
            argv,
            timeout_seconds=arguments.get("timeout_seconds") if isinstance(arguments.get("timeout_seconds"), int) else None,
        )
    except SandboxPolicyError as exc:
        evidence = record_evidence(
            context.run_id,
            "verification",
            f"Sandbox command blocked: {exc}",
            passed=False,
            payload={"argv": argv, "reason": str(exc)},
            home=context.home,
        )
        return ToolCallResult(
            call_id=str(arguments.get("call_id") or "direct"),
            name="zeus.sandbox_command",
            status="blocked",
            summary=str(exc),
            evidence_ids=[evidence.evidence_id],
        )
    evidence = record_command_evidence(context.run_id, result, home=context.home)
    artifacts = [path for path in (result.artifact_path, result.stdout_artifact_path, result.stderr_artifact_path) if path]
    return ToolCallResult(
        call_id=str(arguments.get("call_id") or "direct"),
        name="zeus.sandbox_command",
        status="completed" if evidence.passed else "failed",
        summary=f"Command exited with {result.exit_code}.",
        evidence_ids=[evidence.evidence_id],
        artifact_paths=artifacts,
        result={"exit_code": result.exit_code, "timed_out": result.timed_out, "argv": result.argv},
    )


@_DEFAULT_REGISTRY.register(
    "zeus.diff_gate",
    "Inspect workspace changes and forbidden path hits.",
    risk_level="low",
    requires_approval=False,
)
def _diff_gate(context: ToolContext, arguments: dict[str, Any]) -> ToolCallResult:
    report = diff_gate(context.run_id, home=context.home)
    return ToolCallResult(
        call_id=str(arguments.get("call_id") or "direct"),
        name="zeus.diff_gate",
        status="completed" if report.allowed else "blocked",
        summary=report.summary,
        artifact_paths=[report.artifact_path] if report.artifact_path else [],
        result=report.model_dump(mode="json"),
    )


@_DEFAULT_REGISTRY.register(
    "zeus.search_memory",
    "Search local Zeus session memory.",
    risk_level="low",
    requires_approval=False,
)
def _search_memory(context: ToolContext, arguments: dict[str, Any]) -> ToolCallResult:
    query = str(arguments.get("query") or "")
    rows = StateStore(context.home).search_messages(query, limit=10)
    return ToolCallResult(
        call_id=str(arguments.get("call_id") or "direct"),
        name="zeus.search_memory",
        status="completed",
        summary=f"Found {len(rows)} memory row(s).",
        result={"rows": rows},
    )
