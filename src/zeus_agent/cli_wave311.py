from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.real_mcp_runtime import build_real_mcp_contract


def register_wave311_commands(app: typer.Typer) -> None:
    @app.command("mcp-runtime")
    def mcp_runtime(
        scenario: str = typer.Option("status", "--scenario"),
        server_id: str = typer.Option("mcp.github", "--server-id"),
        include_tools: str = typer.Option("", "--include-tools"),
        exclude_tools: str = typer.Option("", "--exclude-tools"),
        resources_requested: bool = typer.Option(False, "--resources"),
        prompts_requested: bool = typer.Option(False, "--prompts"),
        source_pinned: bool = typer.Option(True, "--source-pinned/--source-unpinned"),
        description: str = typer.Option("Pinned MCP server manifest for governed Zeus runtime.", "--description"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_real_mcp_contract(
            scenario=scenario,
            server_id=server_id,
            include_tools=_csv(include_tools),
            exclude_tools=_csv(exclude_tools),
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
            source_pinned=source_pinned,
            description=description,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
