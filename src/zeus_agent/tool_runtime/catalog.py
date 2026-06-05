from __future__ import annotations

from typing import Final

from .models import JsonObject, ToolDefinition, ToolsetDefinition
from .registry import ToolRuntimeRegistry

_FOUR_TOOL_SETS: Final = frozenset({"files", "research", "github", "memory", "security"})
_TOOLSET_SPECS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    ("files", "Files", ("read", "write", "patch", "search")),
    ("research", "Research", ("web_search", "source_pin", "claim_check", "community_scan")),
    ("github", "GitHub", ("repo_inspect", "issue_search", "pull_request_read", "commit_diff")),
    ("memory", "Memory", ("fact_extract", "fact_review", "export", "delete")),
    ("security", "Security", ("lease_check", "secret_scan", "threat_model", "approval_request")),
    ("terminal", "Terminal", ("plan", "run", "capture")),
    ("browser", "Browser", ("open", "inspect", "screenshot")),
    ("mcp", "MCP", ("discover", "compile", "quarantine")),
    ("providers", "Providers", ("list", "route", "fallback")),
    ("wiki", "LLM Wiki", ("page_render", "page_update", "link_graph")),
    ("skills", "Skills", ("propose", "evaluate", "promote")),
    ("sandbox", "Sandbox", ("plan", "execute", "cleanup")),
    ("gateway", "Gateway", ("pair", "dispatch", "audit")),
    ("api", "API", ("chat_completion", "response", "run")),
    ("workflow", "Workflow", ("job_create", "job_resume", "job_cancel")),
    ("cron", "Cron", ("schedule", "dry_run", "recursion_guard")),
    ("plugins", "Plugins", ("manifest_validate", "permission_check", "quarantine")),
    ("trajectory", "Trajectory", ("export", "redact", "replay_plan")),
    ("batch", "Batch", ("submit", "status", "eval")),
    ("eval", "Evaluation", ("dataset_load", "score", "regression")),
    ("observability", "Observability", ("trace", "audit", "evidence_bundle")),
    ("ontology", "Ontology", ("candidate", "conflict", "provenance")),
    ("objective", "Objective", ("interview", "contract", "acceptance")),
    ("orchestration", "Orchestration", ("dag_plan", "scope_check", "worker_bundle")),
    ("release", "Release", ("boundary_scan", "notes", "gate")),
)


def native_tool_catalog() -> tuple[ToolsetDefinition, ...]:
    return tuple(
        _toolset(toolset_id=toolset_id, display_name=display_name, verbs=verbs)
        for toolset_id, display_name, verbs in _TOOLSET_SPECS
    )


def register_native_tool_catalog(
    runtime: ToolRuntimeRegistry,
    *,
    toolsets: tuple[ToolsetDefinition, ...] | None = None,
) -> ToolRuntimeRegistry:
    for toolset in toolsets or native_tool_catalog():
        runtime.register_toolset(toolset)
    return runtime


def native_tool_catalog_payload() -> JsonObject:
    catalog = native_tool_catalog()
    tool_count = sum(len(toolset.tools) for toolset in catalog)
    return {
        "toolset_count": len(catalog),
        "tool_count": tool_count,
        "source": "local",
        "live_production_claimed": False,
        "toolsets": [
            {
                "toolset_id": toolset.toolset_id,
                "display_name": toolset.display_name,
                "tool_count": len(toolset.tools),
                "capability_ids": [tool.capability_id for tool in toolset.tools],
            }
            for toolset in catalog
        ],
    }


def _toolset(
    *,
    toolset_id: str,
    display_name: str,
    verbs: tuple[str, ...],
) -> ToolsetDefinition:
    expected_count = 4 if toolset_id in _FOUR_TOOL_SETS else 3
    if len(verbs) != expected_count:
        raise AssertionError("invalid native toolset cardinality")
    return ToolsetDefinition(
        toolset_id="native.{0}".format(toolset_id),
        display_name=display_name,
        tools=tuple(_tool(toolset_id=toolset_id, display_name=display_name, verb=verb) for verb in verbs),
    )


def _tool(*, toolset_id: str, display_name: str, verb: str) -> ToolDefinition:
    name = "{0}.{1}".format(toolset_id, verb.replace("_", "."))
    return ToolDefinition(
        name=name,
        description="{0} {1} under Zeus Kernel authority.".format(
            display_name,
            verb.replace("_", " "),
        ),
        capability_id="api.tool.{0}".format(name),
        source="local",
        input_schema={
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "User-scoped request for the governed tool.",
                },
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "evidence": {"type": "object"},
            },
        },
    )
