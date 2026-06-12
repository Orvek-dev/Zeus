from __future__ import annotations

import json
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

# Per-surface STATIC table (same doctrine as the Claude Code hook): the proxy
# sees OpenAI-style function names from arbitrary hosts, so it maps a small
# set of well-known aliases and falls through to a conservative unregistered
# capability for everything else.
_TERMINAL_TOOLS: Final = frozenset(
    {"bash", "exec", "shell", "run", "run_command", "execute_command", "terminal", "process"}
)
_WEB_TOOLS: Final = frozenset(
    {"web_search", "web_fetch", "fetch", "browse", "browser", "http_get", "search_web", "curl"}
)
_FS_READ_TOOLS: Final = frozenset(
    {"read", "read_file", "cat", "list_dir", "ls", "glob", "grep", "find_files"}
)
_FS_WRITE_TOOLS: Final = frozenset(
    {"write", "write_file", "edit", "edit_file", "apply_patch", "create_file", "append_file"}
)

_TERMINAL_BY_SIDE_EFFECT: Final[dict[tuple[SideEffectClass, Reversibility], str]] = {
    (SideEffectClass.none, Reversibility.reversible): "terminal.run.read",
    (SideEffectClass.local_write, Reversibility.compensable): "terminal.run.local",
    (SideEffectClass.account_write, Reversibility.compensable): "terminal.run.package",
    (SideEffectClass.account_write, Reversibility.irreversible): "terminal.run.external",
}


class MappedToolCall:
    def __init__(self, capability_id: str, args: dict[str, JsonValue]) -> None:
        self.capability_id = capability_id
        self.args = args


def map_tool_call_for_host(host, name: str, arguments_json: str) -> MappedToolCall:
    """Host-aware mapping at the proxy gate. The proxy intercepts a model's
    tool_call BEFORE the host's own pre-tool hook runs, so when we know the
    host we consult ITS authoritative table first — otherwise hermes meta/read
    tools (search_files, skills_list, ...) would fall through to host.tool.* and
    ASK-storm. Composition, not duplication: defer to the adapter's mapper."""
    from zeus_agent.decision_api_runtime import HostKind

    if host is HostKind.hermes:
        from zeus_agent.adapters.hermes.mapping import map_hermes_tool_call

        mapped = map_hermes_tool_call(name, _parse_arguments(arguments_json))
        return MappedToolCall(mapped.capability_id, dict(mapped.args))
    return map_proxy_tool_call(name, arguments_json)


def map_proxy_tool_call(name: str, arguments_json: str) -> MappedToolCall:
    tool = name.strip().lower()
    arguments = _parse_arguments(arguments_json)
    if tool in _TERMINAL_TOOLS:
        command = str(arguments.get("command", arguments.get("cmd", "")))
        risk = classify_command(command)
        capability_id = _TERMINAL_BY_SIDE_EFFECT.get(
            (risk.side_effect, risk.reversibility), "terminal.run.external"
        )
        return MappedToolCall(
            capability_id, {"command": command, "command_risk": list(risk.reasons)}
        )
    if tool in _WEB_TOOLS:
        url = str(arguments.get("url", arguments.get("query", "")))
        args: dict[str, JsonValue] = {"url": url}
        host = urlparse(url.strip()).hostname
        if host:
            args["network_host"] = host
        return MappedToolCall("web.fetch", args)
    if tool in _FS_READ_TOOLS:
        return MappedToolCall("fs.read", _path_args(arguments))
    if tool in _FS_WRITE_TOOLS:
        return MappedToolCall("fs.write", _path_args(arguments))
    if name.startswith("mcp__"):
        parts = name.split("__")
        server = parts[1] if len(parts) > 1 else "unknown"
        mcp_tool = parts[2] if len(parts) > 2 else "unknown"
        return MappedToolCall("mcp.{0}.{1}".format(server, mcp_tool), {})
    # Unknown function → unregistered capability → conservative ASK downstream.
    return MappedToolCall("host.tool.{0}".format(tool or "unnamed"), {})


def seed_proxy_capability_store() -> CapabilityStore:
    """Static capability table for the llm_proxy surface."""
    return CapabilityStore(
        (
            _builtin("llm.generate", VerbClass.generate, SideEffectClass.none, Reversibility.reversible,
                     "Call a language model through the governed proxy"),
            _builtin("llm.model_switch", VerbClass.transform, SideEffectClass.none, Reversibility.reversible,
                     "Rewrite a request to a policy-approved alternate model"),
            _builtin("agent.todo.update", VerbClass.transform, SideEffectClass.none, Reversibility.reversible,
                     "Update the host agent's internal task plan"),
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
        input_summary="llm tool-call input",
        output_summary="llm tool-call output",
        side_effect=side_effect,
        reversibility=reversibility,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=CapabilityStatus.active,
    )


def _parse_arguments(arguments_json: str) -> dict[str, JsonValue]:
    try:
        parsed = json.loads(arguments_json) if arguments_json.strip() else {}
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _path_args(arguments: dict[str, JsonValue]) -> dict[str, JsonValue]:
    for key in ("file_path", "path", "filename", "target_file"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return {"path": value.strip()}
    return {}
