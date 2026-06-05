from __future__ import annotations

import json
from datetime import datetime
from json import JSONDecodeError
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.runtime_lease import RuntimeLease


def register_wave89_commands(app: typer.Typer) -> None:
    @app.command("live-transport-lease")
    def live_transport_lease(
        readiness_json: str = typer.Option(..., "--readiness-json"),
        lease_json: str = typer.Option(..., "--lease-json"),
        runtime_kind: str = typer.Option(..., "--runtime-kind"),
        capability_id: str = typer.Option(..., "--capability-id"),
        credential_scope: Optional[str] = typer.Option(None, "--credential-scope"),
        network_host: Optional[str] = typer.Option(None, "--network-host"),
        budget_required: int = typer.Option(1, "--budget-required"),
        evidence_target: str = typer.Option(..., "--evidence-target"),
        now: Optional[str] = typer.Option(None, "--now"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            readiness = LiveExecutionReadinessResult.model_validate_json(readiness_json)
            lease = RuntimeLease.model_validate_json(lease_json)
            parsed_now = _parse_now(now)
        except (JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_transport_lease",
                    "error": str(exc),
                    "live_production_claimed": False,
                    "network_opened": False,
                },
                as_json=as_json,
            )
            raise typer.Exit(code=1)
        result = LiveTransportLeaseRuntime().bind(
            readiness=readiness,
            lease=lease,
            runtime_kind=runtime_kind,
            capability_id=capability_id,
            credential_scope=credential_scope,
            network_host=network_host,
            budget_required=budget_required,
            evidence_target=evidence_target,
            now=parsed_now,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _parse_now(raw_value: Optional[str]) -> Optional[datetime]:
    if raw_value is None:
        return None
    return datetime.fromisoformat(raw_value)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
