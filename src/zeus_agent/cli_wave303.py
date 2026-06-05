from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.gateway_live_delivery_runtime import build_gateway_live_delivery_contract


def register_wave303_commands(app: typer.Typer) -> None:
    @app.command("gateway-live-delivery")
    def gateway_live_delivery(
        scenario: str = typer.Option("status", "--scenario"),
        secret_ref: str = typer.Option("env://ZEUS_RC4_GATEWAY_TOKEN", "--secret-ref"),
        target: str = typer.Option("slack://ops", "--target"),
        message: str = typer.Option("Zeus gateway live delivery checkpoint", "--message"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_gateway_live_delivery_contract(
            scenario=scenario,
            secret_ref=secret_ref,
            target=target,
            message=message,
            home=home,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
