from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationResult
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime


def register_wave95_commands(app: typer.Typer) -> None:
    @app.command("live-executor-release")
    def live_executor_release(
        authorization_json: str = typer.Option(..., "--authorization-json"),
        executor_kind: str = typer.Option(..., "--executor-kind"),
        release_ref: str = typer.Option(..., "--release-ref"),
        idempotency_key: str = typer.Option(..., "--idempotency-key"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            authorization = LiveExecutionAuthorizationResult.model_validate_json(authorization_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_executor_release",
                    "error": str(exc),
                    "executor_release_granted": False,
                    "execution_allowed": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveExecutorReleaseRuntime().release(
            authorization=authorization,
            executor_kind=executor_kind,
            release_ref=release_ref,
            idempotency_key=idempotency_key,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
