from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer


def register_g006_commands(app: typer.Typer) -> None:
    @app.command("g006-gateway-server")
    def g006_gateway_server(
        bind: str = typer.Option(..., "--bind", help="Loopback bind address."),
        port: int = typer.Option(..., "--port", help="Port to bind."),
        db: Path = typer.Option(..., "--db", help="SQLite database path."),
        ready_file: Optional[Path] = typer.Option(
            None,
            "--ready-file",
            help="Optional ready-file path.",
        ),
        loopback_token: str = typer.Option(..., "--loopback-token", help="Loopback auth token."),
    ) -> None:
        from zeus_agent.gateway_runtime.server import run_gateway_loopback_server

        run_gateway_loopback_server(
            bind=bind,
            port=port,
            db_path=db,
            ready_file=ready_file,
            loopback_token=loopback_token,
        )

    @app.command("g006-gateway-loopback")
    def g006_gateway_loopback(
        home: Optional[Path] = typer.Option(None, "--home", help="Optional home directory."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        from zeus_agent.g006_gateway_scenarios import g006_gateway_loopback_payload

        _print_payload(g006_gateway_loopback_payload(home=home), as_json=as_json)

    @app.command("g006-gateway-idempotency")
    def g006_gateway_idempotency(
        home: Optional[Path] = typer.Option(None, "--home", help="Optional home directory."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        from zeus_agent.g006_gateway_scenarios import g006_gateway_idempotency_payload

        _print_payload(g006_gateway_idempotency_payload(home=home), as_json=as_json)

    @app.command("g006-gateway-fail-closed")
    def g006_gateway_fail_closed(
        secret_like: str = typer.Option(..., "--secret-like", help="Sample secret-like value."),
        home: Optional[Path] = typer.Option(None, "--home", help="Optional home directory."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        from zeus_agent.g006_gateway_scenarios import g006_gateway_fail_closed_payload

        _print_payload(g006_gateway_fail_closed_payload(secret_like, home=home), as_json=as_json)

    @app.command("g006-eval")
    def g006_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        from zeus_agent.eval.g006 import run_g006_eval

        _print_payload(run_g006_eval(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
