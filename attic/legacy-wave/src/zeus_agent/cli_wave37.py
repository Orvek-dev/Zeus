from __future__ import annotations

import json
from datetime import datetime
from json import JSONDecodeError
from typing import Optional

import typer
from pydantic import ValidationError

from zeus_agent.live_beta_runtime import (
    LiveBetaActivationRequest,
    LiveBetaActivationRuntime,
)
from zeus_agent.runtime_lease import RuntimeLease


def register_wave37_commands(app: typer.Typer) -> None:
    @app.command("live-beta-activate")
    def live_beta_activate(
        request_json: str = typer.Option(..., "--request-json"),
        lease_json: str = typer.Option(..., "--lease-json"),
        now: Optional[str] = typer.Option(None, "--now"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            request = LiveBetaActivationRequest.model_validate(json.loads(request_json))
            lease = RuntimeLease.model_validate(json.loads(lease_json))
            parsed_now = _parse_now(now)
        except (JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_beta_activation",
                    "error": str(exc),
                    "live_beta_claimed": False,
                    "live_production_claimed": False,
                    "network_opened": False,
                    "handler_executed": False,
                },
                as_json=as_json,
            )
            raise typer.Exit(code=1)
        result = LiveBetaActivationRuntime().activate(request, lease=lease, now=parsed_now)
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
