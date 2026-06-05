from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult


def register_wave112_commands(app: typer.Typer) -> None:
    @app.command("live-remote-executor-preflight")
    def live_remote_executor_preflight(
        policy_json: str = typer.Option(..., "--policy-json"),
        handoff_json: str = typer.Option(..., "--handoff-json"),
        executor_kind: str = typer.Option(..., "--executor-kind"),
        executor_ref: str = typer.Option(..., "--executor-ref"),
        idempotency_key: str = typer.Option(..., "--idempotency-key"),
        teardown_ref: str = typer.Option(..., "--teardown-ref"),
        timeout_ms: int = typer.Option(1500, "--timeout-ms"),
        retry_attempts: int = typer.Option(0, "--retry-attempts"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            policy = LiveRemoteTransportPolicyResult.model_validate_json(policy_json)
            handoff = LiveRemoteCredentialHandoffResult.model_validate_json(handoff_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_remote_executor_preflight",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveRemoteExecutorPreflightRuntime().plan(
            policy=policy,
            handoff=handoff,
            executor_kind=executor_kind,
            executor_ref=executor_ref,
            idempotency_key=idempotency_key,
            teardown_ref=teardown_ref,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
