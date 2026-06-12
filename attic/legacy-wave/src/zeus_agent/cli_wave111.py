from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffRuntime
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult


def register_wave111_commands(app: typer.Typer) -> None:
    @app.command("live-remote-credential-handoff")
    def live_remote_credential_handoff(
        policy_json: str = typer.Option(..., "--policy-json"),
        secret_material_json: str = typer.Option(..., "--secret-material-json"),
        handoff_ref: str = typer.Option(..., "--handoff-ref"),
        auth_scheme: str = typer.Option("bearer", "--auth-scheme"),
        header_name: str = typer.Option("Authorization", "--header-name"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            policy = LiveRemoteTransportPolicyResult.model_validate_json(policy_json)
            secret_material = LiveSecretMaterialResult.model_validate_json(secret_material_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_remote_credential_handoff",
                    "error": str(exc),
                    "network_opened": False,
                    "raw_secret_returned": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveRemoteCredentialHandoffRuntime().prepare(
            policy=policy,
            secret_material=secret_material,
            handoff_ref=handoff_ref,
            auth_scheme=auth_scheme,
            header_name=header_name,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
