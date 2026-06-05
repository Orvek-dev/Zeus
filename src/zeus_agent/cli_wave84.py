from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.live_operator_proof_runtime import LiveOperatorProofRuntime


def register_wave84_commands(app: typer.Typer) -> None:
    @app.command("live-operator-proof")
    def live_operator_proof(
        proof_id: str = typer.Option(..., "--proof-id"),
        operator_id: str = typer.Option(..., "--operator-id"),
        handoff_manifest_id: Optional[str] = typer.Option(None, "--handoff-manifest-id"),
        execution_plan_id: Optional[str] = typer.Option(None, "--execution-plan-id"),
        proof_ref: Optional[str] = typer.Option(None, "--proof-ref"),
        reviewed_risk: list[str] = typer.Option([], "--reviewed-risk"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveOperatorProofRuntime().record(
            proof_id=proof_id,
            operator_id=operator_id,
            handoff_manifest_id=handoff_manifest_id,
            execution_plan_id=execution_plan_id,
            proof_ref=proof_ref,
            reviewed_risks=tuple(reviewed_risk),
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
