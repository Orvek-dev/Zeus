from __future__ import annotations

import re
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.mcp_runtime.catalog import McpCatalogEntry
from zeus_agent.mcp_runtime.catalog import curated_mcp_catalog_payload
from zeus_agent.mcp_runtime.catalog import default_mcp_catalog_entries
from zeus_agent.mcp_runtime.facade import McpFacade
from zeus_agent.mcp_runtime.manager import McpDiscoveryClient
from zeus_agent.mcp_runtime.manager import McpRuntimeManager
from zeus_agent.mcp_runtime.manager_models import McpRuntimeServerSpec
from zeus_agent.mcp_runtime.models import McpServerManifest
from zeus_agent.mcp_runtime.models import McpToolManifest
from zeus_agent.real_mcp_runtime.models import RealMcpContract
from zeus_agent.real_mcp_runtime.models import RealMcpDecision
from zeus_agent.real_mcp_runtime.models import RealMcpScenario
from zeus_agent.security.credentials import redact_secret_spans

_TARGET_VERSION: Final = "v1.2.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.2.0.real_mcp_runtime"
_DEFAULT_SERVER_ID: Final = "mcp.github"
_SAFE_DESCRIPTION: Final = "Pinned MCP server manifest for governed Zeus runtime."
_TOOL_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_MCP_ID_PATTERN: Final = _TOOL_ID_PATTERN
_PROMPT_INJECTION_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous instructions",
    "reveal secret",
    "reveal secrets",
    "system prompt",
)
_DESCRIPTION_SECRET_PATTERN: Final = re.compile(
    r"(?i)(api[ _-]?key|private[ _-]?key|token|password|secret)\s*[=:]\s*[^\s\"'}]+"
    r"|sk-[A-Za-z0-9][A-Za-z0-9._-]*"
    r"|ghp_[A-Za-z0-9_]+"
    r"|github_pat_[A-Za-z0-9_]+"
    r"|glpat-[A-Za-z0-9_-]+"
    r"|xox[abp]-[A-Za-z0-9-]+",
)
_SUPPORTED_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "catalog",
        "setup-dry-run",
        "list",
        "inspect",
        "test-loopback",
        "login-dry-run",
        "blocked-resource-prompt",
        "blocked-unpinned",
        "blocked-prompt-injection",
    },
)


def build_real_mcp_contract(
    *,
    scenario: str = "status",
    server_id: str = _DEFAULT_SERVER_ID,
    include_tools: tuple[str, ...] = (),
    exclude_tools: tuple[str, ...] = (),
    resources_requested: bool = False,
    prompts_requested: bool = False,
    source_pinned: bool = True,
    description: str = _SAFE_DESCRIPTION,
) -> RealMcpContract:
    safe_scenario = scenario.strip()
    safe_server_id = server_id.strip()
    if _has_unsafe_identifier_marker(safe_server_id) or _has_description_secret_material(description):
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("secret_like_mcp_input_blocked",),
        )
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_real_mcp_scenario",),
        )
    parsed_scenario = _parse_scenario(safe_scenario)
    if not _MCP_ID_PATTERN.fullmatch(safe_server_id):
        return _contract(
            decision="blocked",
            scenario=parsed_scenario,
            blocked_reasons=("malformed_mcp_server_id",),
        )
    tool_reasons = _tool_policy_block_reasons(include_tools=include_tools, exclude_tools=exclude_tools)
    if tool_reasons:
        return _contract(
            decision="blocked",
            scenario=parsed_scenario,
            blocked_reasons=tool_reasons,
            selected_server_id=safe_server_id,
        )
    entries = default_mcp_catalog_entries()
    entry = _entry(entries, safe_server_id)
    if entry is None:
        return _contract(
            decision="blocked",
            scenario=parsed_scenario,
            blocked_reasons=("unknown_mcp_server",),
            selected_server_id=safe_server_id,
        )
    selected_include = _selected_include(entry, include_tools)
    selected_exclude = _normalize_tools(exclude_tools)
    if parsed_scenario == "status":
        return _contract(decision="report", scenario="status", selected_server_id=entry.server_id)
    if parsed_scenario == "catalog":
        return _contract(
            decision="report",
            scenario="catalog",
            selected_server_id=entry.server_id,
            catalog=curated_mcp_catalog_payload(),
        )
    if parsed_scenario == "setup-dry-run":
        return _setup_dry_run(entry=entry, include_tools=selected_include, exclude_tools=selected_exclude)
    if parsed_scenario == "list":
        return _list(entry=entry, include_tools=selected_include, exclude_tools=selected_exclude)
    if parsed_scenario == "inspect":
        return _inspect(
            entry=entry,
            include_tools=selected_include,
            exclude_tools=selected_exclude,
            source_pinned=source_pinned,
            description=description,
        )
    if parsed_scenario == "test-loopback":
        return _test_loopback(
            entry=entry,
            include_tools=selected_include,
            exclude_tools=selected_exclude,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
            source_pinned=source_pinned,
            description=description,
        )
    if parsed_scenario == "login-dry-run":
        return _login_dry_run(entry)
    if parsed_scenario == "blocked-resource-prompt":
        return _blocked_resource_prompt(
            entry=entry,
            resources_requested=resources_requested or True,
            prompts_requested=prompts_requested or True,
        )
    if parsed_scenario == "blocked-unpinned":
        return _contract(
            decision="blocked",
            scenario="blocked-unpinned",
            blocked_reasons=("mcp_server_unpinned",),
            selected_server_id=entry.server_id,
            selected_transport=entry.transport,
            selected_source_ref=entry.source_ref,
            include_tools=selected_include,
            exclude_tools=selected_exclude,
        )
    return _inspect(
        entry=entry,
        include_tools=selected_include,
        exclude_tools=selected_exclude,
        source_pinned=source_pinned,
        description=description,
        forced_scenario="blocked-prompt-injection",
    )


def _parse_scenario(value: str) -> RealMcpScenario:
    if value == "status":
        return "status"
    if value == "catalog":
        return "catalog"
    if value == "setup-dry-run":
        return "setup-dry-run"
    if value == "list":
        return "list"
    if value == "inspect":
        return "inspect"
    if value == "test-loopback":
        return "test-loopback"
    if value == "login-dry-run":
        return "login-dry-run"
    if value == "blocked-resource-prompt":
        return "blocked-resource-prompt"
    if value == "blocked-unpinned":
        return "blocked-unpinned"
    if value == "blocked-prompt-injection":
        return "blocked-prompt-injection"
    return "status"


def _setup_dry_run(
    *,
    entry: McpCatalogEntry,
    include_tools: tuple[str, ...],
    exclude_tools: tuple[str, ...],
) -> RealMcpContract:
    return _contract(
        decision="report",
        scenario="setup-dry-run",
        selected_server_id=entry.server_id,
        selected_transport=entry.transport,
        selected_source_ref=entry.source_ref,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        setup_plan={
            "server_id": entry.server_id,
            "transport": entry.transport,
            "state": "dry_run",
            "source_ref": entry.source_ref,
            "source_pinned": entry.source_pinned,
            "include_tools": list(include_tools),
            "exclude_tools": list(exclude_tools),
            "resources_enabled": False,
            "prompts_enabled": False,
            "server_started": False,
            "credential_material_accessed": False,
        },
    )


def _list(
    *,
    entry: McpCatalogEntry,
    include_tools: tuple[str, ...],
    exclude_tools: tuple[str, ...],
) -> RealMcpContract:
    specs = _server_specs(entry=entry, include_tools=include_tools, exclude_tools=exclude_tools)
    return _contract(
        decision="report",
        scenario="list",
        selected_server_id=entry.server_id,
        selected_transport=entry.transport,
        selected_source_ref=entry.source_ref,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        list_snapshot={
            "server_count": len(specs),
            "servers": [spec.model_dump(mode="json") for spec in specs],
            "server_started": False,
            "network_opened": False,
            "credential_material_accessed": False,
        },
    )


def _inspect(
    *,
    entry: McpCatalogEntry,
    include_tools: tuple[str, ...],
    exclude_tools: tuple[str, ...],
    source_pinned: bool,
    description: str,
    forced_scenario: Optional[RealMcpScenario] = None,
) -> RealMcpContract:
    scenario: RealMcpScenario = forced_scenario or "inspect"
    if _effective_tools(include_tools=include_tools, exclude_tools=exclude_tools) == ():
        return _contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("mcp_filter_no_tools",),
            selected_server_id=entry.server_id,
            selected_transport=entry.transport,
            selected_source_ref=entry.source_ref,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
        )
    manifest = _manifest(
        entry=entry,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        source_pinned=source_pinned,
        description=description,
    )
    result = McpFacade().plan_manifest(manifest)
    blocked = result.decision == "blocked"
    reasons = tuple(result.evidence.quarantine_reasons)
    if scenario == "blocked-prompt-injection" and not reasons:
        reasons = ("mcp_prompt_injection_detected",)
        blocked = True
    return _contract(
        decision="blocked" if blocked else "report",
        scenario=scenario,
        blocked_reasons=_normalize_reasons(reasons),
        selected_server_id=entry.server_id,
        selected_transport=entry.transport,
        selected_source_ref=entry.source_ref,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        compiled_tool_names=tuple(result.dispatch.tool_names),
        inspect_result=result.model_dump(mode="json"),
    )


def _test_loopback(
    *,
    entry: McpCatalogEntry,
    include_tools: tuple[str, ...],
    exclude_tools: tuple[str, ...],
    resources_requested: bool,
    prompts_requested: bool,
    source_pinned: bool,
    description: str,
) -> RealMcpContract:
    if resources_requested or prompts_requested:
        return _blocked_resource_prompt(
            entry=entry,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
        )
    if not source_pinned:
        return _contract(
            decision="blocked",
            scenario="test-loopback",
            blocked_reasons=("mcp_server_unpinned",),
            selected_server_id=entry.server_id,
            selected_transport=entry.transport,
            selected_source_ref=entry.source_ref,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
        )
    if _effective_tools(include_tools=include_tools, exclude_tools=exclude_tools) == ():
        return _contract(
            decision="blocked",
            scenario="test-loopback",
            blocked_reasons=("mcp_filter_no_tools",),
            selected_server_id=entry.server_id,
            selected_transport=entry.transport,
            selected_source_ref=entry.source_ref,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
        )
    manifest = _manifest(
        entry=entry,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        source_pinned=source_pinned,
        description=description,
    )
    if manifest.quarantine_state == "quarantined":
        return _contract(
            decision="blocked",
            scenario="test-loopback",
            blocked_reasons=_normalize_reasons(manifest.quarantine_reasons),
            selected_server_id=entry.server_id,
            selected_transport=entry.transport,
            selected_source_ref=entry.source_ref,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
        )
    spec = _server_spec(entry=entry, include_tools=include_tools, exclude_tools=exclude_tools, source_pinned=True)
    client = _FakeMcpDiscoveryClient(manifest)
    manager = McpRuntimeManager()
    manager.register_server(spec, client)
    start = manager.start(entry.server_id)
    refresh = manager.refresh(entry.server_id)
    compiled = manager.compile_tools()
    stopped_count = manager.shutdown_all()
    ready = (
        start.decision == "allowed"
        and refresh.decision == "allowed"
        and len(compiled) > 0
        and stopped_count == 1
        and client.started is False
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="test-loopback",
        blocked_reasons=() if ready else _normalize_reasons((start.reason, refresh.reason)),
        selected_server_id=entry.server_id,
        selected_transport=entry.transport,
        selected_source_ref=entry.source_ref,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        compiled_tool_names=tuple(tool.name for tool in compiled),
        real_mcp_runtime_ready=ready,
        test_result={
            "start": start.model_dump(mode="json"),
            "refresh": refresh.model_dump(mode="json"),
            "compiled_tool_count": len(compiled),
            "compiled_tool_names": [tool.name for tool in compiled],
            "stopped_count": stopped_count,
            "cleanup_receipt": "fake-mcp-client-stopped",
        },
        server_started=False,
        subprocess_started=False,
    )


def _login_dry_run(entry: McpCatalogEntry) -> RealMcpContract:
    return _contract(
        decision="report",
        scenario="login-dry-run",
        selected_server_id=entry.server_id,
        selected_transport=entry.transport,
        selected_source_ref=entry.source_ref,
        login_plan={
            "server_id": entry.server_id,
            "credential_scope": entry.credential_scope,
            "material_required": entry.requires_credential,
            "material_accessed": False,
            "network_opened": False,
            "login_state": "dry_run",
            "approval_required": entry.requires_credential,
        },
    )


def _blocked_resource_prompt(
    *,
    entry: McpCatalogEntry,
    resources_requested: bool,
    prompts_requested: bool,
) -> RealMcpContract:
    reasons: list[str] = []
    if resources_requested:
        reasons.append("mcp_resources_require_separate_policy")
    if prompts_requested:
        reasons.append("mcp_prompts_require_separate_policy")
    return _contract(
        decision="blocked",
        scenario="blocked-resource-prompt",
        blocked_reasons=tuple(reasons),
        selected_server_id=entry.server_id,
        selected_transport=entry.transport,
        selected_source_ref=entry.source_ref,
        resources_enabled=False,
        prompts_enabled=False,
    )


def _contract(
    *,
    decision: RealMcpDecision,
    scenario: RealMcpScenario,
    blocked_reasons: tuple[str, ...] = (),
    selected_server_id: Optional[str] = None,
    selected_transport: Optional[str] = None,
    selected_source_ref: Optional[str] = None,
    include_tools: tuple[str, ...] = (),
    exclude_tools: tuple[str, ...] = (),
    compiled_tool_names: tuple[str, ...] = (),
    catalog: Optional[dict[str, JsonValue]] = None,
    setup_plan: Optional[dict[str, JsonValue]] = None,
    list_snapshot: Optional[dict[str, JsonValue]] = None,
    inspect_result: Optional[dict[str, JsonValue]] = None,
    test_result: Optional[dict[str, JsonValue]] = None,
    login_plan: Optional[dict[str, JsonValue]] = None,
    resources_enabled: bool = False,
    prompts_enabled: bool = False,
    real_mcp_runtime_ready: bool = False,
    server_started: bool = False,
    subprocess_started: bool = False,
) -> RealMcpContract:
    entries = default_mcp_catalog_entries()
    result = RealMcpContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="real_mcp_runtime",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        real_mcp_runtime_ready=real_mcp_runtime_ready,
        production_ready=False,
        catalog_entry_count=len(entries),
        beta_enabled_count=len([entry for entry in entries if entry.beta_enabled]),
        selected_server_id=selected_server_id,
        selected_transport=selected_transport,
        selected_source_ref=selected_source_ref,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        compiled_tool_count=len(compiled_tool_names),
        compiled_tool_names=compiled_tool_names,
        catalog=catalog,
        setup_plan=setup_plan,
        list_snapshot=list_snapshot,
        inspect_result=inspect_result,
        test_result=test_result,
        login_plan=login_plan,
        resources_enabled=resources_enabled,
        prompts_enabled=prompts_enabled,
        server_started=server_started,
        subprocess_started=subprocess_started,
        network_opened=False,
        non_loopback_network_opened=False,
        handler_executed=False,
        credential_material_accessed=False,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _entry(entries: tuple[McpCatalogEntry, ...], server_id: str) -> Optional[McpCatalogEntry]:
    for entry in entries:
        if entry.server_id == server_id:
            return entry
    return None


def _selected_include(entry: McpCatalogEntry, include_tools: tuple[str, ...]) -> tuple[str, ...]:
    normalized = _normalize_tools(include_tools)
    return normalized or entry.include_tools


def _normalize_tools(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return tuple(seen)


def _server_specs(
    *,
    entry: McpCatalogEntry,
    include_tools: tuple[str, ...],
    exclude_tools: tuple[str, ...],
) -> tuple[McpRuntimeServerSpec, ...]:
    return (_server_spec(entry=entry, include_tools=include_tools, exclude_tools=exclude_tools, source_pinned=True),)


def _server_spec(
    *,
    entry: McpCatalogEntry,
    include_tools: tuple[str, ...],
    exclude_tools: tuple[str, ...],
    source_pinned: bool,
) -> McpRuntimeServerSpec:
    return McpRuntimeServerSpec(
        server_id=entry.server_id,
        transport=entry.transport,
        display_name=entry.display_name,
        source_ref=entry.source_ref,
        source_pinned=source_pinned,
        endpoint=entry.endpoint,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        resources_enabled=False,
        prompts_enabled=False,
    )


def _manifest(
    *,
    entry: McpCatalogEntry,
    include_tools: tuple[str, ...],
    exclude_tools: tuple[str, ...],
    source_pinned: bool,
    description: str,
) -> McpServerManifest:
    tools = []
    for tool_name in _effective_tools(include_tools=include_tools, exclude_tools=exclude_tools):
        tools.append(
            McpToolManifest(
                name=_tool_name(tool_name),
                capability_id="{0}.{1}".format(entry.server_id, tool_name),
                description="{0} tool".format(tool_name),
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            ),
        )
    return McpServerManifest(
        server_id=entry.server_id,
        display_name=entry.display_name,
        source_ref=entry.source_ref if source_pinned else None,
        source_pinned=source_pinned,
        description=description,
        tools=tuple(tools),
    )


def _tool_name(tool_name: str) -> str:
    return tool_name if tool_name.startswith("mcp.") else "mcp.{0}".format(tool_name)


def _effective_tools(*, include_tools: tuple[str, ...], exclude_tools: tuple[str, ...]) -> tuple[str, ...]:
    excluded = set(exclude_tools)
    return tuple(tool for tool in include_tools if tool not in excluded)


def _tool_policy_block_reasons(*, include_tools: tuple[str, ...], exclude_tools: tuple[str, ...]) -> tuple[str, ...]:
    reasons: list[str] = []
    for value in (*include_tools, *exclude_tools):
        if _has_unsafe_identifier_marker(value):
            reasons.append("secret_like_mcp_input_blocked")
        elif not _TOOL_ID_PATTERN.fullmatch(value.removeprefix("mcp.")):
            reasons.append("malformed_mcp_tool_id")
    return tuple(dict.fromkeys(reasons))


def _has_secret_like(value: str) -> bool:
    normalized = value.strip()
    return redact_secret_spans(normalized) != normalized


def _has_unsafe_identifier_marker(value: str) -> bool:
    normalized = value.strip()
    lowered = normalized.lower()
    return _has_secret_like(normalized) or any(marker in lowered for marker in _PROMPT_INJECTION_MARKERS)


def _has_description_secret_material(value: str) -> bool:
    normalized = value.strip()
    return _DESCRIPTION_SECRET_PATTERN.search(normalized) is not None and redact_secret_spans(normalized) != normalized


def _normalize_reasons(values: tuple[str, ...]) -> tuple[str, ...]:
    mapped: list[str] = []
    for value in values:
        if value.startswith("mcp_server_prompt_injection") or value.startswith("mcp_tool_prompt_injection"):
            candidate = "mcp_prompt_injection_detected"
        else:
            candidate = value
        if candidate not in mapped:
            mapped.append(candidate)
    return tuple(mapped)


class _FakeMcpDiscoveryClient(McpDiscoveryClient):
    def __init__(self, manifest: McpServerManifest) -> None:
        self._manifest = manifest
        self.started = False
        self.request_count = 0

    def start(self) -> None:
        self.started = True

    def list_tools(self) -> JsonValue:
        self.request_count += 1
        return {
            "description": self._manifest.description,
            "tools": [tool.model_dump(mode="json") for tool in self._manifest.tools],
        }

    def stop(self) -> None:
        self.started = False

    def metadata(self) -> dict[str, JsonValue]:
        return {"request_count": self.request_count, "subprocess_started": False, "network_opened": False}
