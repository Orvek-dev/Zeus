from __future__ import annotations

import json
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease


def register_wave59_commands(app: typer.Typer) -> None:
    @app.command("live-preflight")
    def live_preflight(
        request_json: str = typer.Option(..., "--request-json"),
        lease_json: str = typer.Option(..., "--lease-json"),
        home: Optional[Path] = typer.Option(None, "--home"),
        now: Optional[str] = typer.Option(None, "--now"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            request = LivePreflightRequest.model_validate(json.loads(request_json))
            lease = RuntimeLease.model_validate(json.loads(lease_json))
            parsed_now = _parse_now(now)
        except (JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_preflight",
                    "error": str(exc),
                    "live_beta_ready": False,
                    "live_production_claimed": False,
                    "network_opened": False,
                    "handler_executed": False,
                },
                as_json=as_json,
            )
            raise typer.Exit(code=1)
        result = LivePreflightRuntime(home=home).evaluate(request, lease=lease, now=parsed_now)
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
