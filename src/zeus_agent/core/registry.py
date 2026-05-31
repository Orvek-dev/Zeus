"""Provider, model, tool, and publishing registries."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from zeus_agent.paths import config_dir, ensure_private_dir, registry_dir
from zeus_agent.schemas.registry import GitHubPublishPlan, ModelRoute, ProviderAuthConfig, ToolDefinition
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import read_json, write_private_json


def add_provider(
    provider: str,
    env_var: str,
    *,
    base_url: str | None = None,
    enabled: bool = True,
    home: Path | None = None,
) -> ProviderAuthConfig:
    config = ProviderAuthConfig(
        provider=provider,
        env_var=env_var,
        base_url=base_url,
        enabled=enabled,
    )
    providers = {item.provider: item for item in list_providers(home=home)}
    providers[provider] = config
    _write_list(_providers_path(home), [item.model_dump(mode="json") for item in providers.values()])
    EventLog(home).append(new_trace_event("registry.provider.added", payload={"provider": provider, "env_var": env_var}))
    return config


def list_providers(*, home: Path | None = None) -> list[ProviderAuthConfig]:
    return [ProviderAuthConfig.model_validate(item) for item in _read_list(_providers_path(home))]


def provider_status(*, home: Path | None = None) -> list[dict[str, object]]:
    return [
        {
            **provider.model_dump(mode="json"),
            "configured": bool(os.environ.get(provider.env_var)),
        }
        for provider in list_providers(home=home)
    ]


def add_model_route(
    purpose: str,
    provider: str,
    model: str,
    *,
    priority: int = 100,
    max_cost_usd: float = 0.0,
    home: Path | None = None,
) -> ModelRoute:
    route = ModelRoute(
        purpose=purpose,
        provider=provider,
        model=model,
        priority=priority,
        max_cost_usd=max_cost_usd,
    )
    routes = list_model_routes(home=home)
    routes.append(route)
    routes = sorted(routes, key=lambda item: (item.purpose, item.priority))
    _write_list(_routes_path(home), [item.model_dump(mode="json") for item in routes])
    EventLog(home).append(new_trace_event("registry.model_route.added", payload={"route_id": route.route_id, "provider": provider, "model": model}))
    return route


def list_model_routes(*, home: Path | None = None) -> list[ModelRoute]:
    return [ModelRoute.model_validate(item) for item in _read_list(_routes_path(home))]


def register_tool(
    name: str,
    description: str,
    *,
    risk_level: Literal["low", "medium", "high"] = "medium",
    command: list[str] | None = None,
    network_access: Literal["none", "allowlist", "open"] = "none",
    home: Path | None = None,
) -> ToolDefinition:
    tool = ToolDefinition(
        name=name,
        description=description,
        risk_level=risk_level,
        command=command or [],
        requires_approval=(risk_level != "low" or network_access != "none"),
        network_access=network_access,
    )
    tools = list_tools(home=home)
    tools.append(tool)
    _write_list(_tools_path(home), [item.model_dump(mode="json") for item in tools])
    EventLog(home).append(new_trace_event("registry.tool.registered", payload={"tool_id": tool.tool_id, "name": name, "risk_level": risk_level}))
    return tool


def list_tools(*, home: Path | None = None) -> list[ToolDefinition]:
    return [ToolDefinition.model_validate(item) for item in _read_list(_tools_path(home))]


def create_github_publish_plan(
    repo: str,
    *,
    remote: str = "origin",
    branch: str = "main",
    home: Path | None = None,
) -> GitHubPublishPlan:
    plan = GitHubPublishPlan(
        repo=repo,
        remote=remote,
        branch=branch,
        required_checks=[
            "uv run --extra dev pytest",
            "uv run python -m compileall -q src tests",
            "zeus CLI smoke test with isolated ZEUS_HOME",
            "manual review of SECURITY.md and docs/IMPLEMENTATION_STATUS.md",
        ],
        blocked_until_milestones=[],
        ready=False,
        notes=[
            "This plan stores publishing intent only; it does not initialize git, commit, push, or create a repository.",
            "Mark ready only after the user explicitly asks for GitHub publishing.",
        ],
    )
    plans = list_github_publish_plans(home=home)
    plans.append(plan)
    _write_list(_github_plans_path(home), [item.model_dump(mode="json") for item in plans])
    EventLog(home).append(new_trace_event("registry.github_publish_plan.created", payload={"plan_id": plan.plan_id, "repo": repo}))
    return plan


def list_github_publish_plans(*, home: Path | None = None) -> list[GitHubPublishPlan]:
    return [GitHubPublishPlan.model_validate(item) for item in _read_list(_github_plans_path(home))]


def _providers_path(home: Path | None) -> Path:
    return config_dir(home) / "providers.json"


def _routes_path(home: Path | None) -> Path:
    return config_dir(home) / "model_routes.json"


def _tools_path(home: Path | None) -> Path:
    return registry_dir(home) / "tools.json"


def _github_plans_path(home: Path | None) -> Path:
    return registry_dir(home) / "github_publish_plans.json"


def _read_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return read_json(path)


def _write_list(path: Path, values: list[dict]) -> Path:
    ensure_private_dir(path.parent)
    return write_private_json(path, values)
