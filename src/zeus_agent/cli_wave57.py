from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.approval_cockpit_runtime import ApprovalCockpitRuntime


def register_wave57_commands(app: typer.Typer) -> None:
    @app.command("approvals")
    def approvals(
        approval_id: Optional[str] = typer.Option(None, "--approval-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = ApprovalCockpitRuntime().build(approval_id=approval_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
