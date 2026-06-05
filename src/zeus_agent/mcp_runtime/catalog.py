from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from .manager_models import McpRuntimeServerSpec, McpTransportKind

CatalogState = Literal["planned_wave", "dry_run"]
_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, strict=True)


class McpCatalogEntry(BaseModel):
    model_config = _MODEL_CONFIG

    server_id: str
    display_name: str
    transport: McpTransportKind
    source_ref: str
    source_pinned: bool = True
    state: CatalogState = "planned_wave"
    beta_enabled: bool = False
    include_tools: tuple[str, ...] = ()
    exclude_tools: tuple[str, ...] = ()
    endpoint: Optional[str] = None
    toolset_hint: str
    requires_credential: bool = False
    credential_scope: Optional[str] = None
    resources_enabled: bool = False
    prompts_enabled: bool = False
    unsafe_markers_detected: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False


def default_mcp_catalog_entries() -> tuple[McpCatalogEntry, ...]:
    raw_entries = (
        ("mcp.github", "GitHub", "stdio", "github", ("repo.search", "issues.list", "pulls.list")),
        ("mcp.filesystem", "Filesystem", "stdio", "filesystem", ("file.read", "file.search")),
        ("mcp.git", "Git", "stdio", "git", ("git.status", "git.diff")),
        ("mcp.sqlite", "SQLite", "stdio", "sqlite", ("db.query", "db.schema")),
        ("mcp.postgres", "Postgres", "stdio", "postgres", ("db.query", "db.schema")),
        ("mcp.playwright", "Playwright", "http", "playwright", ("browser.inspect", "browser.screenshot")),
        ("mcp.fetch", "Fetch", "http", "fetch", ("web.fetch", "web.head")),
        ("mcp.docs", "Docs", "stdio", "docs", ("docs.search", "docs.open")),
        ("mcp.slack", "Slack", "http", "slack", ("message.search", "channel.list")),
        ("mcp.google_drive", "Google Drive", "http", "google-drive", ("drive.search", "drive.read")),
        ("mcp.notion", "Notion", "http", "notion", ("page.search", "database.query")),
        ("mcp.linear", "Linear", "http", "linear", ("issue.search", "project.list")),
        ("mcp.jira", "Jira", "http", "jira", ("issue.search", "project.list")),
        ("mcp.asana", "Asana", "http", "asana", ("task.search", "project.list")),
        ("mcp.browser", "Browser", "http", "browser", ("page.inspect", "page.click")),
        ("mcp.terminal", "Terminal", "stdio", "terminal", ("command.plan", "command.run")),
        ("mcp.sandbox", "Sandbox", "stdio", "sandbox", ("sandbox.exec", "sandbox.snapshot")),
        ("mcp.docker", "Docker", "stdio", "docker", ("container.list", "container.logs")),
        ("mcp.kubernetes", "Kubernetes", "stdio", "kubernetes", ("pod.list", "event.list")),
        ("mcp.supabase", "Supabase", "http", "supabase", ("db.query", "edge.logs")),
        ("mcp.cloudflare", "Cloudflare", "http", "cloudflare", ("worker.list", "deploy.inspect")),
        ("mcp.vercel", "Vercel", "http", "vercel", ("deployment.list", "log.search")),
        ("mcp.figma", "Figma", "http", "figma", ("file.inspect", "component.search")),
        ("mcp.gmail", "Gmail", "http", "gmail", ("mail.search", "mail.read")),
        ("mcp.calendar", "Calendar", "http", "calendar", ("event.search", "availability.check")),
    )
    entries: list[McpCatalogEntry] = []
    for index, (server_id, display_name, transport, source_slug, include_tools) in enumerate(raw_entries):
        beta_enabled = index < 10
        endpoint = "http://127.0.0.1:0/mcp/{0}".format(source_slug) if transport == "http" else None
        credential_scope = _mcp_credential_scope(server_id)
        entries.append(
            McpCatalogEntry(
                server_id=server_id,
                display_name=display_name,
                transport=transport,
                source_ref="catalog://mcp/{0}@2026-06-04".format(source_slug),
                state="dry_run" if beta_enabled else "planned_wave",
                beta_enabled=beta_enabled,
                include_tools=include_tools,
                endpoint=endpoint,
                toolset_hint=source_slug,
                requires_credential=credential_scope is not None,
                credential_scope=credential_scope,
            ),
        )
    return tuple(entries)


def _mcp_credential_scope(server_id: str) -> Optional[str]:
    return {
        "mcp.github": "external.github.readonly",
        "mcp.postgres": "external.postgres.readonly",
        "mcp.slack": "external.slack.readonly",
        "mcp.google_drive": "external.google_drive.readonly",
        "mcp.notion": "external.notion.readonly",
        "mcp.linear": "external.linear.readonly",
        "mcp.jira": "external.jira.readonly",
        "mcp.asana": "external.asana.readonly",
        "mcp.supabase": "external.supabase.readonly",
        "mcp.cloudflare": "external.cloudflare.readonly",
        "mcp.vercel": "external.vercel.readonly",
        "mcp.figma": "external.figma.readonly",
        "mcp.gmail": "external.gmail.readonly",
        "mcp.calendar": "external.calendar.readonly",
    }.get(server_id)


def mcp_catalog_server_specs(
    entries: tuple[McpCatalogEntry, ...] | None = None,
) -> tuple[McpRuntimeServerSpec, ...]:
    specs: list[McpRuntimeServerSpec] = []
    for entry in entries or default_mcp_catalog_entries():
        if not entry.beta_enabled:
            continue
        specs.append(
            McpRuntimeServerSpec(
                server_id=entry.server_id,
                transport=entry.transport,
                display_name=entry.display_name,
                source_ref=entry.source_ref,
                source_pinned=entry.source_pinned,
                endpoint=entry.endpoint,
                include_tools=entry.include_tools,
                exclude_tools=entry.exclude_tools,
                resources_enabled=False,
                prompts_enabled=False,
            ),
        )
    return tuple(specs)


def curated_mcp_catalog_payload() -> dict[str, object]:
    entries = default_mcp_catalog_entries()
    beta_enabled = [entry for entry in entries if entry.beta_enabled]
    unsafe = [entry for entry in entries if entry.unsafe_markers_detected or not entry.source_pinned]
    return {
        "catalog_entry_count": len(entries),
        "beta_enabled_count": len(beta_enabled),
        "unsafe_catalog_entry_count": len(unsafe),
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "server_specs": [spec.model_dump(mode="json") for spec in mcp_catalog_server_specs(entries)],
        "resources_prompts_wrappers_enabled": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }


__all__ = [
    "McpCatalogEntry",
    "curated_mcp_catalog_payload",
    "default_mcp_catalog_entries",
    "mcp_catalog_server_specs",
]
