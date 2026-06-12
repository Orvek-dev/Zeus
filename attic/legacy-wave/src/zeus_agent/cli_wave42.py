from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.mcp_cockpit_runtime import McpCockpitRuntime
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime


def register_wave42_commands(app: typer.Typer) -> None:
    @app.command("mcp")
    def mcp(
        server_id: Optional[str] = typer.Option(None, "--server-id"),
        add_server: Optional[str] = typer.Option(None, "--add", help="Add a catalog MCP server to local quarantined config."),
        list_config: bool = typer.Option(False, "--list-config", help="List local MCP server config."),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        runtime = McpSettingsRuntime(home or default_zeus_home())
        if add_server is not None:
            _print_payload(runtime.add(server_ref=add_server).to_payload(), as_json=as_json)
            return
        if list_config:
            _print_payload(runtime.list().to_payload(), as_json=as_json)
            return
        result = McpCockpitRuntime().build(server_id=server_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
