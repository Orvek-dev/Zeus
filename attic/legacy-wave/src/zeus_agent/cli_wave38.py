from __future__ import annotations

import json
from json import JSONDecodeError

import typer

from zeus_agent.mcp_runtime import normalize_tools_list_result


def register_wave38_commands(app: typer.Typer) -> None:
    @app.command("mcp-discovery-normalize")
    def mcp_discovery_normalize(
        server_id: str = typer.Option(..., "--server-id"),
        server_label: str = typer.Option(..., "--server-label"),
        transport: str = typer.Option("stdio", "--transport"),
        tools_json: str = typer.Option(..., "--tools-json"),
        trusted_server: bool = typer.Option(False, "--trusted-server"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            if transport not in {"stdio", "http"}:
                raise ValueError("invalid_mcp_transport")
            snapshot = normalize_tools_list_result(
                json.loads(tools_json),
                server_id=server_id,
                server_label=server_label,
                transport=transport,
                trusted_server=trusted_server,
            )
        except (JSONDecodeError, ValueError, TypeError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_mcp_discovery",
                    "error": str(exc),
                    "handler_executed": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            raise typer.Exit(code=1)
        _print_payload(snapshot.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
