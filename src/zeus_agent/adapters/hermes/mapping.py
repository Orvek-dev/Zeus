from __future__ import annotations

from typing import Final
from urllib.parse import urlparse

from pydantic import JsonValue

from zeus_agent.command_risk_runtime import classify_command
from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.trust_loop_runtime import Reversibility

# Static per-host table (doctrine). Pinned against the hermes-agent tool names
# from the design notes — adjust alongside the pinned hermes version.
_TERMINAL: Final = frozenset({"terminal", "run_command", "shell", "bash", "execute"})
_FS_READ: Final = frozenset({"read_file", "file_read", "list_files", "search_files", "grep"})
_FS_WRITE: Final = frozenset({"write_file", "file_write", "edit_file", "create_file"})
_WEB: Final = frozenset(
    {
        "web_search",
        "web_extract",
        "fetch_url",
        "extract_url",
        "browser_navigate",
        "browser",
        "http_request",
    }
)
_SEND: Final = frozenset({"send_message", "send_email", "post_message"})
_TODO: Final = frozenset({"todo", "todos", "todo_list", "update_todo", "task_list"})
_META_READ: Final = frozenset(
    {"skills_list", "skills", "skill_view", "skill_search", "list_skills", "skill_info"}
)

_TERMINAL_BY_RISK: Final[dict[tuple[SideEffectClass, Reversibility], str]] = {
    (SideEffectClass.none, Reversibility.reversible): "terminal.run.read",
    (SideEffectClass.local_write, Reversibility.compensable): "terminal.run.local",
    (SideEffectClass.account_write, Reversibility.compensable): "terminal.run.package",
    (SideEffectClass.account_write, Reversibility.irreversible): "terminal.run.external",
}


class MappedHermesCall:
    def __init__(self, capability_id: str, args: dict[str, JsonValue]) -> None:
        self.capability_id = capability_id
        self.args = args


def map_hermes_tool_call(tool: str, args: dict[str, JsonValue]) -> MappedHermesCall:
    name = tool.strip().lower()
    if name in _TERMINAL:
        command = str(args.get("command", args.get("cmd", "")))
        risk = classify_command(command)
        capability_id = _TERMINAL_BY_RISK.get(
            (risk.side_effect, risk.reversibility), "terminal.run.external"
        )
        return MappedHermesCall(capability_id, {"command": command, "command_risk": list(risk.reasons)})
    if name in _FS_READ:
        return MappedHermesCall("fs.read", _path_args(args))
    if name in _META_READ:
        return MappedHermesCall("fs.read", {})  # read-only host introspection
    if name in _FS_WRITE:
        return MappedHermesCall("fs.write", _path_args(args))
    if name in _WEB:
        url = str(args.get("url", args.get("query", "")))
        mapped: dict[str, JsonValue] = {"url": url}
        host = urlparse(url.strip()).hostname
        if host:
            mapped["network_host"] = host
        return MappedHermesCall("web.fetch", mapped)
    if name in _SEND:
        mapped = {"recipient": str(args.get("to", args.get("recipient", "")))}
        host = args.get("host")
        if isinstance(host, str) and host.strip():
            mapped["network_host"] = host.strip()
        return MappedHermesCall("msg.send", mapped)
    if name in _TODO:
        return MappedHermesCall("agent.todo.update", {})
    if name.startswith("mcp__"):
        parts = tool.split("__")
        server = parts[1] if len(parts) > 1 else "unknown"
        mcp_tool = parts[2] if len(parts) > 2 else "unknown"
        return MappedHermesCall("mcp.{0}.{1}".format(server, mcp_tool), {})
    return MappedHermesCall("host.tool.{0}".format(name or "unnamed"), {})


def _path_args(args: dict[str, JsonValue]) -> dict[str, JsonValue]:
    for key in ("path", "file_path", "filename"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return {"path": value.strip()}
    return {}
