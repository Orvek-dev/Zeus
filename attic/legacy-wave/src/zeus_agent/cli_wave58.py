from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.approval_receipt_runtime import ApprovalReceiptRuntime


def register_wave58_commands(app: typer.Typer) -> None:
    @app.command("approval-receipt")
    def approval_receipt(
        approval_id: str = typer.Option(..., "--approval-id"),
        principal_id: str = typer.Option(..., "--principal-id"),
        objective_id: str = typer.Option(..., "--objective-id"),
        capability_id: str = typer.Option(..., "--capability-id"),
        ttl_minutes: int = typer.Option(30, "--ttl-minutes"),
        now: Optional[str] = typer.Option(None, "--now"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        parsed_now = _parse_now(now)
        result = ApprovalReceiptRuntime().record(
            approval_id=approval_id,
            principal_id=principal_id,
            objective_id=objective_id,
            capability_id=capability_id,
            now=parsed_now,
            ttl_minutes=ttl_minutes,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _parse_now(raw_value: Optional[str]) -> Optional[datetime]:
    if raw_value is None:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise typer.BadParameter("--now must be an ISO-8601 datetime") from exc


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
