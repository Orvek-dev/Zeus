from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.live_profile_runtime import LiveProfileRuntime


def register_wave63_commands(app: typer.Typer) -> None:
    @app.command("live-profile")
    def live_profile(
        surface_id: str = typer.Option(..., "--surface-id"),
        principal_id: str = typer.Option(..., "--principal-id"),
        objective_id: str = typer.Option(..., "--objective-id"),
        delivery_target: Optional[str] = typer.Option(None, "--delivery-target"),
        allowlisted_delivery_target: list[str] = typer.Option(
            [],
            "--allowlisted-delivery-target",
        ),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveProfileRuntime(home or default_zeus_home()).build(
            surface_id=surface_id,
            principal_id=principal_id,
            objective_id=objective_id,
            delivery_target=delivery_target,
            allowlisted_delivery_targets=tuple(allowlisted_delivery_target),
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
