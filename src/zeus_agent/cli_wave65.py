from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.live_dry_run_runtime import LiveDryRunRuntime


def register_wave65_commands(app: typer.Typer) -> None:
    @app.command("live-dry-run")
    def live_dry_run(
        surface_id: str = typer.Option(..., "--surface-id"),
        principal_id: str = typer.Option(..., "--principal-id"),
        objective_id: str = typer.Option(..., "--objective-id"),
        delivery_target: Optional[str] = typer.Option(None, "--delivery-target"),
        allowlisted_delivery_target: list[str] = typer.Option(
            [],
            "--allowlisted-delivery-target",
        ),
        execute_live: bool = typer.Option(False, "--execute-live"),
        check_credentials: bool = typer.Option(False, "--check-credentials"),
        now: Optional[str] = typer.Option(None, "--now"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveDryRunRuntime(home or default_zeus_home()).run(
            surface_id=surface_id,
            principal_id=principal_id,
            objective_id=objective_id,
            delivery_target=delivery_target,
            allowlisted_delivery_targets=tuple(allowlisted_delivery_target),
            execute_live=execute_live,
            check_credentials=check_credentials,
            now=_parse_now(now),
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _parse_now(raw_value: Optional[str]) -> Optional[datetime]:
    if raw_value is None:
        return None
    return datetime.fromisoformat(raw_value)


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
