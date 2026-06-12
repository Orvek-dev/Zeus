from __future__ import annotations

import hashlib
import json
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
_MEMORY_READ: Final = frozenset(
    {"memory", "memory_read", "memory_search", "search_memory", "recall_memory", "list_memory"}
)
_MEMORY_WRITE: Final = frozenset(
    {"memory_write", "remember", "save_memory", "store_memory", "upsert_memory"}
)
_MEMORY_WRITE_INTENTS: Final = frozenset({"write", "save", "remember", "store", "upsert"})
_MEMORY_WRITE_KEYS: Final = frozenset(
    {"content", "text", "value", "note", "fact", "entry", "message", "user", "assistant"}
)
_MEMORY_READ_ONLY_KEYS: Final = frozenset(
    {"query", "pattern", "glob", "limit", "offset", "search", "filter"}
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
    if name in _MEMORY_READ or name in _MEMORY_WRITE:
        write = (
            name in _MEMORY_WRITE
            or _memory_intent(args) in _MEMORY_WRITE_INTENTS
            or _memory_payload_suggests_write(args)
        )
        return MappedHermesCall(
            "agent.memory.write" if write else "agent.memory.read",
            _memory_args(args, write=write),
        )
    if name in _FS_WRITE:
        return MappedHermesCall("fs.write", _path_args(args))
    if name in _WEB:
        url = _url_arg(args)
        mapped: dict[str, JsonValue] = {"url": url}
        host = urlparse(url.strip()).hostname
        if host:
            mapped["network_host"] = host.strip()
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
    for key in ("directory", "dir", "root", "query", "pattern", "glob"):
        value = args.get(key)
        if isinstance(value, str) and _looks_like_path(value):
            return {"path": value.strip()}
    return {}


def _url_arg(args: dict[str, JsonValue]) -> str:
    for key in ("url", "uri", "href", "link"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    urls = args.get("urls")
    if isinstance(urls, list):
        for value in urls:
            if isinstance(value, str) and value.strip():
                return value.strip()
    query = args.get("query")
    if isinstance(query, str) and urlparse(query.strip()).scheme in {"http", "https"}:
        return query.strip()
    return ""


def _looks_like_path(value: str) -> bool:
    stripped = value.strip()
    return bool(
        stripped
        and (
            "/" in stripped
            or stripped.startswith("~")
            or stripped.startswith(".")
            or stripped in {".ssh", ".aws", ".kube", ".gnupg"}
        )
    )


def _memory_intent(args: dict[str, JsonValue]) -> str:
    for key in ("action", "operation", "mode", "intent"):
        value = args.get(key)
        if isinstance(value, str):
            return value.strip().lower()
    return ""


def _memory_payload_suggests_write(args: dict[str, JsonValue]) -> bool:
    if not args:
        return False
    keys = {key.strip().lower() for key in args}
    if keys and keys <= _MEMORY_READ_ONLY_KEYS:
        return False
    if keys & _MEMORY_WRITE_KEYS:
        return True
    for value in args.values():
        if isinstance(value, str) and value.strip().startswith(("+", "+user:", "+assistant:")):
            return True
    return False


def _memory_args(args: dict[str, JsonValue], *, write: bool) -> dict[str, JsonValue]:
    if not write:
        return {"operation": "read"}
    return {
        "operation": "write",
        # Never place raw proposed memory in a decision receipt. The dedicated
        # memory gate owns candidate storage and promotion; the proxy receipt
        # only needs a stable payload identity for replay/approval matching.
        "content_hash": _stable_hash(args),
    }


def _stable_hash(value: JsonValue) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
