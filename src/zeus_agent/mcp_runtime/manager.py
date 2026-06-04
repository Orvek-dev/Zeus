from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from pydantic import JsonValue, ValidationError

from .models import JsonObject, McpServerManifest, McpToolManifest
from .manager_models import (
    McpDiscoveryClient,
    McpRuntimeDiscoveryResult,
    McpRuntimeServerSpec,
    McpTransportKind,
)


@dataclass
class _ServerRecord:
    spec: McpRuntimeServerSpec
    client: McpDiscoveryClient
    started: bool = False


class McpRuntimeManager:
    def __init__(self) -> None:
        self._records: dict[str, _ServerRecord] = {}
        self._compiled: dict[str, tuple[McpToolManifest, ...]] = {}
        self._lock = threading.RLock()

    def register_server(
        self,
        spec: McpRuntimeServerSpec,
        client: McpDiscoveryClient,
    ) -> None:
        with self._lock:
            if spec.server_id in self._records:
                raise ValueError("duplicate_mcp_server")
            self._records[spec.server_id] = _ServerRecord(spec=spec, client=client)

    def start(self, server_id: str) -> McpRuntimeDiscoveryResult:
        with self._lock:
            record = self._require_record(server_id)
            blocked = _preflight_block(record.spec)
            if blocked is not None:
                return _blocked(record.spec, blocked)
            if record.started:
                return McpRuntimeDiscoveryResult(
                    decision="allowed",
                    reason="mcp_server_already_started",
                    server_id=record.spec.server_id,
                    transport=record.spec.transport,
                    request_count=_request_count(record.client),
                )
            record.client.start()
            record.started = True
            return McpRuntimeDiscoveryResult(
                decision="allowed",
                reason="mcp_server_started",
                server_id=record.spec.server_id,
                transport=record.spec.transport,
                request_count=_request_count(record.client),
            )

    def refresh(self, server_id: str) -> McpRuntimeDiscoveryResult:
        with self._lock:
            record = self._require_record(server_id)
            if not record.started:
                return _blocked(record.spec, "mcp_server_not_started")
            self._compiled.pop(record.spec.server_id, None)
            try:
                manifest, discovered_count, compiled = _manifest_from_discovery(
                    record.spec,
                    record.client.list_tools(),
                )
            except (TypeError, ValueError, ValidationError):
                return _blocked(
                    record.spec,
                    "malformed_mcp_discovery",
                    request_count=_request_count(record.client),
                )
            if manifest.quarantine_state == "quarantined":
                return McpRuntimeDiscoveryResult(
                    decision="blocked",
                    reason="mcp_manifest_quarantined",
                    server_id=record.spec.server_id,
                    transport=record.spec.transport,
                    manifest=manifest,
                    discovered_tool_count=discovered_count,
                    request_count=_request_count(record.client),
                )
            self._compiled[record.spec.server_id] = compiled
            return McpRuntimeDiscoveryResult(
                decision="allowed",
                reason="mcp_discovery_refreshed",
                server_id=record.spec.server_id,
                transport=record.spec.transport,
                manifest=manifest,
                discovered_tool_count=discovered_count,
                compiled_tools=compiled,
                request_count=_request_count(record.client),
            )

    def compile_tools(self) -> tuple[McpToolManifest, ...]:
        with self._lock:
            tools = [tool for value in self._compiled.values() for tool in value]
            return tuple(sorted(tools, key=lambda tool: tool.name))

    def metadata_snapshot(self) -> tuple[JsonObject, ...]:
        with self._lock:
            rows: list[JsonObject] = []
            for record in self._records.values():
                rows.append({
                    "server_id": record.spec.server_id,
                    "transport": record.spec.transport,
                    "started": record.started,
                    "request_count": _request_count(record.client),
                    "compiled_tool_count": len(self._compiled.get(record.spec.server_id, ())),
                })
            return tuple(sorted(rows, key=lambda row: str(row["server_id"])))

    def shutdown_all(self) -> int:
        with self._lock:
            stopped = 0
            for record in self._records.values():
                if record.started:
                    record.client.stop()
                    record.started = False
                    stopped += 1
                self._compiled.pop(record.spec.server_id, None)
            return stopped

    def _require_record(self, server_id: str) -> _ServerRecord:
        record = self._records.get(server_id)
        if record is None:
            raise ValueError("unknown_mcp_server")
        return record


def _preflight_block(spec: McpRuntimeServerSpec) -> Optional[str]:
    if not spec.source_pinned or spec.source_ref is None:
        return "mcp_server_unpinned"
    if spec.resources_enabled or spec.prompts_enabled:
        return "mcp_resource_prompt_wrappers_disabled"
    if spec.transport == "http" and not _is_loopback_endpoint(spec.endpoint):
        return "mcp_http_non_loopback"
    return None


def _manifest_from_discovery(
    spec: McpRuntimeServerSpec,
    raw: JsonValue,
) -> tuple[McpServerManifest, int, tuple[McpToolManifest, ...]]:
    if not isinstance(raw, dict):
        raise ValueError("malformed_mcp_discovery")
    raw_tools = raw.get("tools")
    if not isinstance(raw_tools, list) or not raw_tools:
        raise ValueError("malformed_mcp_discovery")
    discovered = [_tool_from_raw(item) for item in raw_tools]
    names = [tool.name for tool in discovered]
    if len(names) != len(set(names)):
        raise ValueError("duplicate_tool_name")
    full_manifest = McpServerManifest(
        server_id=spec.server_id,
        display_name=spec.display_name,
        source_ref=spec.source_ref,
        source_pinned=spec.source_pinned,
        description=str(raw.get("description") or spec.display_name),
        tools=tuple(discovered),
    )
    if full_manifest.quarantine_state == "quarantined":
        return full_manifest, len(discovered), ()
    compiled = tuple(tool for tool in discovered if _included(spec, tool))
    if not compiled:
        raise ValueError("mcp_filter_no_tools")
    filtered_manifest = McpServerManifest(
        server_id=spec.server_id,
        display_name=spec.display_name,
        source_ref=spec.source_ref,
        source_pinned=spec.source_pinned,
        description=str(raw.get("description") or spec.display_name),
        tools=compiled,
    )
    return filtered_manifest, len(discovered), compiled


def _tool_from_raw(value: JsonValue) -> McpToolManifest:
    if not isinstance(value, dict):
        raise ValueError("malformed_mcp_discovery")
    raw_name = value.get("name")
    if not isinstance(raw_name, str):
        raise ValueError("malformed_mcp_discovery")
    name = raw_name if raw_name.startswith("mcp.") else "mcp.{0}".format(raw_name)
    capability_id = value.get("capability_id") or name
    return McpToolManifest(
        name=name,
        capability_id=str(capability_id),
        description=str(value.get("description") or name),
        input_schema=_json_object(value.get("input_schema") or value.get("inputSchema")),
        output_schema=_json_object(value.get("output_schema")),
    )


def _included(spec: McpRuntimeServerSpec, tool: McpToolManifest) -> bool:
    raw_name = tool.name.removeprefix("mcp.")
    names = {tool.name, raw_name}
    if spec.include_tools and not names.intersection(spec.include_tools):
        return False
    return not names.intersection(spec.exclude_tools)


def _json_object(value: JsonValue) -> JsonObject:
    return value if isinstance(value, dict) else {"type": "object", "properties": {}}


def _blocked(
    spec: McpRuntimeServerSpec,
    reason: str,
    *,
    request_count: int = 0,
) -> McpRuntimeDiscoveryResult:
    return McpRuntimeDiscoveryResult(
        decision="blocked",
        reason=reason,
        server_id=spec.server_id,
        transport=spec.transport,
        request_count=request_count,
    )


def _is_loopback_endpoint(endpoint: Optional[str]) -> bool:
    if endpoint is None:
        return False
    parsed = urlparse(endpoint)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _request_count(client: McpDiscoveryClient) -> int:
    value = client.metadata().get("request_count", 0)
    return value if isinstance(value, int) else 0


__all__ = [
    "McpDiscoveryClient",
    "McpRuntimeDiscoveryResult",
    "McpRuntimeManager",
    "McpRuntimeServerSpec",
    "McpTransportKind",
]
