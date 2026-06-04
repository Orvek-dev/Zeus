from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.capability_runtime import SandboxPolicy
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.security.credentials import redact_secret_spans

from .executor_policy import CAPABILITY_BY_ACTION
from .models import ToolSandboxRequest, ToolSandboxResult


def handlers(policy: SandboxPolicy):
    return {
        "sandbox.file.read": lambda broker_payload: _read_file(broker_payload),
        "sandbox.file.write": lambda broker_payload: _write_file(broker_payload),
        "sandbox.command.run": lambda broker_payload: _run_command(policy, broker_payload),
    }


def _read_file(broker_payload: dict) -> dict[str, object]:
    path = Path(str(broker_payload["resolved_path"]))
    return {"content": redact_secret_spans(path.read_text(encoding="utf-8"))}


def _write_file(broker_payload: dict) -> dict[str, object]:
    path = Path(str(broker_payload["resolved_path"]))
    path.write_text(str(broker_payload.get("content", "")), encoding="utf-8")
    return {"written": True, "path": path.name}


def _run_command(policy: SandboxPolicy, broker_payload: dict) -> dict[str, object]:
    return policy.run_command(str(broker_payload["command"]), Path(str(broker_payload["root"])))


def payload_for_broker(
    request: ToolSandboxRequest,
    approved_root: Path,
    scoped_path: str,
) -> dict[str, object]:
    broker_payload: dict[str, object] = {
        "root": approved_root.as_posix(),
        "path": scoped_path,
    }
    if request.path is not None:
        resolved = (approved_root / request.path).resolve()
        broker_payload["sandbox_path"] = request.path
        broker_payload["resolved_path"] = resolved.as_posix()
    if request.content is not None:
        broker_payload["content"] = request.content
    if request.command is not None:
        broker_payload["command"] = request.command
    return broker_payload


def capability_graph() -> CapabilityGraph:
    return CapabilityGraph((
        _descriptor("sandbox.file.read", CapabilityRisk.low, []),
        _descriptor("sandbox.file.write", CapabilityRisk.high, [SideEffect.filesystem_write]),
        _descriptor("sandbox.command.run", CapabilityRisk.high, [SideEffect.local_process]),
    ))


def _descriptor(
    capability_id: str,
    risk: CapabilityRisk,
    side_effects: list[SideEffect],
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=capability_id,
        risk=risk,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        description=capability_id,
        side_effects=side_effects,
    )


def from_broker(
    request: ToolSandboxRequest,
    response: dict,
    evidence_count: int,
) -> ToolSandboxResult:
    result = _redact_json(response.get("result"))
    serialized = json.dumps(result, sort_keys=True)
    return ToolSandboxResult(
        decision=response.get("decision", "error"),
        reason=str(response.get("reason") or response.get("decision") or "error"),
        action=request.action,
        capability_id=_capability_id(request),
        result=result if isinstance(result, dict) else None,
        evidence_count=evidence_count,
        broker_dispatch_used=True,
        evidence_record_created=evidence_count > 0,
        handler_executed=_handler_executed(result),
        network_opened=False,
        safe_env_used=_safe_env_used(result),
        no_secret_echo="sk-" not in serialized and "ghp_" not in serialized,
    )


def blocked_result(request: ToolSandboxRequest, reason: str) -> ToolSandboxResult:
    return ToolSandboxResult(
        decision="blocked",
        reason=redact_secret_spans(reason),
        action=request.action,
        capability_id=_capability_id(request),
        handler_executed=False,
        network_opened=False,
    )


def _redact_json(value):
    if isinstance(value, str):
        return redact_secret_spans(value)
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_json(item) for key, item in value.items()}
    return value


def _safe_env_used(value) -> bool:
    return isinstance(value, dict) and value.get("safe_env", True) is True


def _handler_executed(value) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(value.get("handler_executed", True))


def _capability_id(request: ToolSandboxRequest) -> str:
    return CAPABILITY_BY_ACTION.get(request.action, "sandbox.malformed")
