from __future__ import annotations

from pathlib import Path
from typing import Callable

from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.security.credentials import redact_secret_spans

from .sandbox import SandboxPolicy


def build_wave3_capability_graph() -> CapabilityGraph:
    return CapabilityGraph(
        [
            CapabilityDescriptor(
                capability_id="file.read",
                name="file.read",
                risk=CapabilityRisk.low,
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
                output_schema={"type": "object"},
                description="Read a UTF-8 file from the sandbox root.",
            ),
            CapabilityDescriptor(
                capability_id="text.search",
                name="text.search",
                risk=CapabilityRisk.low,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
                output_schema={"type": "object"},
                description="Search UTF-8 text files under the sandbox root.",
            ),
            CapabilityDescriptor(
                capability_id="terminal.run",
                name="terminal.run",
                risk=CapabilityRisk.high,
                input_schema={
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string"},
                        "argv": {"type": "array", "items": {"type": "string"}},
                    },
                },
                output_schema={"type": "object"},
                description="Run an allowlisted local command in the sandbox root.",
                side_effects=[SideEffect.local_process],
            ),
        ]
    )


def build_wave3_handlers(
    root: Path,
    policy: SandboxPolicy | None = None,
) -> dict[str, Callable[[dict], object]]:
    sandbox_root = root.resolve()
    sandbox_policy = policy or SandboxPolicy()

    def file_read(payload: dict) -> dict[str, object]:
        raw_path = payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return _blocked_file_result("malformed_path")
        decision = sandbox_policy.resolve_path(sandbox_root, raw_path)
        if decision.decision == "blocked" or decision.path is None:
            return _blocked_file_result(decision.reason or "path_blocked")
        if sandbox_policy.protects_credential_path(sandbox_root, decision.path):
            return _blocked_file_result("credential_path")
        if not decision.path.is_file():
            return _blocked_file_result("not_a_file")
        try:
            content = _redact_text(decision.path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            return _blocked_file_result("file_decode_failed")
        return {
            "path": _relative_path(decision.path, sandbox_root),
            "content": content,
        }

    def text_search(payload: dict) -> dict[str, object]:
        raw_query = payload.get("query")
        if not isinstance(raw_query, str) or not raw_query:
            return {"decision": "blocked", "reason": "malformed_query", "query": None, "matches": []}
        raw_path = payload.get("path")
        search_path_text = str(sandbox_root) if raw_path is None else raw_path
        if not isinstance(search_path_text, str) or not search_path_text.strip():
            return {"decision": "blocked", "reason": "malformed_path", "query": raw_query, "matches": []}
        decision = sandbox_policy.resolve_path(sandbox_root, search_path_text)
        if decision.decision == "blocked" or decision.path is None:
            return {
                "decision": "blocked",
                "reason": decision.reason or "path_blocked",
                "query": raw_query,
                "matches": [],
            }
        if sandbox_policy.protects_credential_path(sandbox_root, decision.path):
            return {"decision": "blocked", "reason": "credential_path", "query": raw_query, "matches": []}
        return {
            "query": raw_query,
            "matches": _search_matches(decision.path, sandbox_root, sandbox_policy, raw_query),
        }

    def terminal_run(payload: dict) -> dict[str, object]:
        raw_command = payload.get("argv", payload.get("cmd"))
        if not isinstance(raw_command, (str, list, tuple)):
            return {
                "decision": "blocked",
                "reason": "malformed_command",
                "stdout": "",
                "stderr": "",
                "return_code": None,
            }
        return sandbox_policy.run_command(raw_command, sandbox_root)

    return {
        "file.read": file_read,
        "text.search": text_search,
        "terminal.run": terminal_run,
    }


def _search_matches(
    path: Path,
    root: Path,
    policy: SandboxPolicy,
    query: str,
) -> list[dict[str, object]]:
    files = [path] if path.is_file() else sorted(
        (candidate for candidate in path.rglob("*") if candidate.is_file()),
        key=lambda candidate: _relative_path(candidate, root),
    )
    matches = []
    for file_path in files:
        if policy.protects_credential_path(root, file_path):
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(lines, start=1):
            if query in line:
                matches.append(
                    {
                        "path": _relative_path(file_path, root),
                        "line": index,
                        "snippet": _redact_text(line),
                    }
                )
    return matches


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _blocked_file_result(reason: str) -> dict[str, object]:
    return {
        "decision": "blocked",
        "reason": reason,
        "path": None,
        "content": None,
    }


def _redact_text(value: str) -> str:
    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    return "{0}{1}{2}".format(leading, redact_secret_spans(value.strip()), trailing)
