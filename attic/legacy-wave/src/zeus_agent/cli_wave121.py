from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_production_approval_runtime import LiveProductionApprovalResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimRuntime


def register_wave121_commands(app: typer.Typer) -> None:
    @app.command("live-production-claim")
    def live_production_claim(
        home: Path = typer.Option(Path(".zeus"), "--home"),
        approval_json: str = typer.Option(..., "--approval-json"),
        claim_ref: str = typer.Option(..., "--claim-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            approval = LiveProductionApprovalResult.model_validate_json(approval_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_production_claim",
                    "error": str(exc),
                    "production_claim_recorded": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProductionClaimRuntime().record(home=home, approval=approval, claim_ref=claim_ref)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
