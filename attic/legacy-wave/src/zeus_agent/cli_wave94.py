from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofResult


def register_wave94_commands(app: typer.Typer) -> None:
    @app.command("live-execution-authorization")
    def live_execution_authorization(
        envelope_kind: str = typer.Option(..., "--envelope-kind"),
        envelope_json: str = typer.Option(..., "--envelope-json"),
        operator_proof_json: str = typer.Option(..., "--operator-proof-json"),
        required_risk: list[str] = typer.Option([], "--required-risk"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            envelope = json.loads(envelope_json)
            operator_proof = LiveOperatorProofResult.model_validate_json(operator_proof_json)
        except (ValidationError, json.JSONDecodeError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execution_authorization",
                    "error": str(exc),
                    "execution_allowed": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        if not isinstance(envelope, dict):
            envelope = {}
        result = LiveExecutionAuthorizationRuntime().authorize(
            envelope_kind=envelope_kind,
            envelope=envelope,
            operator_proof=operator_proof,
            required_risks=tuple(required_risk),
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
