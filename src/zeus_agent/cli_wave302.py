from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.mcp_live_server_runtime import build_mcp_live_server_contract


def register_wave302_commands(app: typer.Typer) -> None:
    @app.command("mcp-live-server")
    def mcp_live_server(
        scenario: str = typer.Option("status", "--scenario"),
        secret_ref: str = typer.Option("env://ZEUS_RC3_MCP_TOKEN", "--secret-ref"),
        query: str = typer.Option("Zeus MCP live server checkpoint", "--query"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_mcp_live_server_contract(
            scenario=scenario,
            secret_ref=secret_ref,
            query=query,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
