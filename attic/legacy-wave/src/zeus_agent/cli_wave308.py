from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.mcp_owned_client_live_runtime import build_mcp_owned_client_live_contract


def register_wave308_commands(app: typer.Typer) -> None:
    @app.command("mcp-owned-client-live")
    def mcp_owned_client_live(
        scenario: str = typer.Option("status", "--scenario"),
        endpoint: str = typer.Option("https://mcp.github.local/rpc", "--endpoint"),
        allowed_host: str = typer.Option("mcp.github.local", "--allowed-host"),
        secret_ref: str = typer.Option("env://ZEUS_RC9_MCP_TOKEN", "--secret-ref"),
        server_id: str = typer.Option("mcp.github", "--server-id"),
        tool_name: str = typer.Option("repo.search", "--tool-name"),
        query: str = typer.Option("Zeus MCP owned client live checkpoint", "--query"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_mcp_owned_client_live_contract(
            scenario=scenario,
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            server_id=server_id,
            tool_name=tool_name,
            query=query,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
