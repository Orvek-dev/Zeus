from __future__ import annotations

from typing import Final
from urllib.parse import urlparse

from pydantic import JsonValue

from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityStore,
    CapabilityTrust,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)
from zeus_agent.command_risk_runtime import classify_command
from zeus_agent.trust_loop_runtime import Reversibility

# Resolved open design question: the tool→capability map is a per-host STATIC
# table. Registry-driven inference can come later; a hook must be predictable.
_FS_READ_TOOLS: Final = frozenset(
    {"Read", "Glob", "Grep", "NotebookRead", "LS", "TaskList", "TaskGet"}
)
_FS_WRITE_TOOLS: Final = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
_WEB_TOOLS: Final = frozenset({"WebFetch", "WebSearch"})
_AGENT_TOOLS: Final = frozenset({"Task", "Agent"})

# Bash commands route to one of five terminal capabilities by deterministic
# command classification — so `ls` and `rm -rf` stop sharing one risk profile.
_TERMINAL_BY_SIDE_EFFECT: Final[dict[tuple[SideEffectClass, Reversibility], str]] = {
    (SideEffectClass.none, Reversibility.reversible): "terminal.run.read",
    (SideEffectClass.local_write, Reversibility.compensable): "terminal.run.local",
    (SideEffectClass.account_write, Reversibility.compensable): "terminal.run.package",
    (SideEffectClass.account_write, Reversibility.irreversible): "terminal.run.external",
}


class MappedCall:
    def __init__(self, capability_id: str, args: dict[str, JsonValue]) -> None:
        self.capability_id = capability_id
        self.args = args


def map_tool_call(tool_name: str, tool_input: dict[str, JsonValue]) -> MappedCall:
    name = tool_name.strip()
    if name in _FS_READ_TOOLS:
        return MappedCall("fs.read", _path_args(tool_input))
    if name in _FS_WRITE_TOOLS:
        return MappedCall("fs.write", _path_args(tool_input))
    if name == "Bash":
        command = str(tool_input.get("command", ""))
        risk = classify_command(command)
        capability_id = _TERMINAL_BY_SIDE_EFFECT.get(
            (risk.side_effect, risk.reversibility), "terminal.run.external"
        )
        args: dict[str, JsonValue] = {"command": command, "command_risk": list(risk.reasons)}
        return MappedCall(capability_id, args)
    if name in _WEB_TOOLS:
        args = {}
        url = str(tool_input.get("url", "") or tool_input.get("query", ""))
        host = _host_of(url)
        args["url"] = url
        if host is not None:
            args["network_host"] = host
        return MappedCall("web.fetch", args)
    if name in _AGENT_TOOLS:
        return MappedCall("agent.spawn", {"prompt_chars": len(str(tool_input.get("prompt", "")))})
    if name.startswith("mcp__"):
        parts = name.split("__")
        server = parts[1] if len(parts) > 1 else "unknown"
        tool = parts[2] if len(parts) > 2 else "unknown"
        return MappedCall("mcp.{0}.{1}".format(server, tool), {})
    # Unknown host tool → unregistered capability → conservative ASK downstream.
    return MappedCall("host.tool.{0}".format(name.lower() or "unnamed"), {})


def seed_capability_store() -> CapabilityStore:
    """The static capability table for the Claude Code host."""
    return CapabilityStore(
        (
            _builtin("fs.read", VerbClass.fetch, SideEffectClass.none, Reversibility.reversible,
                     "Read files and search the workspace"),
            _builtin("fs.write", VerbClass.store, SideEffectClass.local_write, Reversibility.compensable,
                     "Edit or create files in the workspace"),
            _builtin("terminal.run.read", VerbClass.observe, SideEffectClass.none, Reversibility.reversible,
                     "Run a read-only shell command"),
            _builtin("terminal.run.local", VerbClass.store, SideEffectClass.local_write, Reversibility.compensable,
                     "Run a shell command that mutates local files"),
            _builtin("terminal.run.package", VerbClass.store, SideEffectClass.account_write, Reversibility.compensable,
                     "Run a package or environment mutation"),
            _builtin("terminal.run.external", VerbClass.publish, SideEffectClass.account_write, Reversibility.irreversible,
                     "Run a network, destructive, or unrecognized command"),
            _builtin("web.fetch", VerbClass.fetch, SideEffectClass.none, Reversibility.reversible,
                     "Fetch a web page or search result (untrusted source)"),
            _builtin("agent.spawn", VerbClass.generate, SideEffectClass.none, Reversibility.reversible,
                     "Spawn a subagent (its own calls are gated individually)"),
        )
    )


def _builtin(
    capability_id: str,
    verb: VerbClass,
    side_effect: SideEffectClass,
    reversibility: Reversibility,
    title: str,
) -> CapabilityRecord:
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=verb,
        title=title,
        input_summary="claude-code tool input",
        output_summary="claude-code tool output",
        side_effect=side_effect,
        reversibility=reversibility,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=CapabilityStatus.active,
    )


def _path_args(tool_input: dict[str, JsonValue]) -> dict[str, JsonValue]:
    for key in ("file_path", "path", "notebook_path", "pattern"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return {"path": value.strip()}
    return {}


def _host_of(url: str) -> str | None:
    host = urlparse(url.strip()).hostname
    return host if host else None
