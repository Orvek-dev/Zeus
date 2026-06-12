from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult


def register_wave125_commands(app: typer.Typer) -> None:
    @app.command("live-credential-injection")
    def live_credential_injection(
        adapter_kind: str = typer.Option(..., "--adapter-kind"),
        claim_json: str = typer.Option(..., "--claim-json"),
        policy_json: str = typer.Option(..., "--policy-json"),
        preflight_json: str = typer.Option(..., "--preflight-json"),
        handoff_json: str = typer.Option(..., "--handoff-json"),
        secret_material_json: str = typer.Option(..., "--secret-material-json"),
        injection_ref: str = typer.Option(..., "--injection-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            claim = LiveProductionClaimResult.model_validate_json(claim_json)
            policy = LiveRemoteTransportPolicyResult.model_validate_json(policy_json)
            preflight = LiveRemoteExecutorPreflightResult.model_validate_json(preflight_json)
            handoff = LiveRemoteCredentialHandoffResult.model_validate_json(handoff_json)
            secret_material = LiveSecretMaterialResult.model_validate_json(secret_material_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_credential_injection",
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "raw_secret_returned": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveCredentialInjectionRuntime().prepare(
            adapter_kind=adapter_kind,
            claim=claim,
            policy=policy,
            preflight=preflight,
            handoff=handoff,
            secret_material=secret_material,
            injection_ref=injection_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
