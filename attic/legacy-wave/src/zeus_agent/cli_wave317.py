from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.zeus_identity_activation_runtime import build_zeus_identity_activation_contract


def register_wave317_commands(app: typer.Typer) -> None:
    @app.command("identity-activation-runtime")
    def identity_activation_runtime(
        scenario: str = typer.Option("identity-status", "--scenario"),
        home: Optional[Path] = typer.Option(None, "--home"),
        message: Optional[str] = typer.Option(None, "--message"),
        objective_id: Optional[str] = typer.Option(None, "--objective-id"),
        lease_id: Optional[str] = typer.Option(None, "--lease-id"),
        approval_id: Optional[str] = typer.Option(None, "--approval-id"),
        credential_binding_ref: Optional[str] = typer.Option(None, "--credential-binding-ref"),
        sandbox_policy_ref: Optional[str] = typer.Option(None, "--sandbox-policy-ref"),
        audit_receipt_ref: Optional[str] = typer.Option(None, "--audit-receipt-ref"),
        operator_note: Optional[str] = typer.Option(None, "--operator-note"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        _ = home
        payload = build_zeus_identity_activation_contract(
            scenario=scenario,
            message=message,
            objective_id=objective_id,
            lease_id=lease_id,
            approval_id=approval_id,
            credential_binding_ref=credential_binding_ref,
            sandbox_policy_ref=sandbox_policy_ref,
            audit_receipt_ref=audit_receipt_ref,
            operator_note=operator_note,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
