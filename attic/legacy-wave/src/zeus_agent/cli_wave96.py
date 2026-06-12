from __future__ import annotations

import json
from json import JSONDecodeError

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseResult
from zeus_agent.live_loopback_executor_runtime import LiveLoopbackExecutorRuntime


def register_wave96_commands(app: typer.Typer) -> None:
    @app.command("live-loopback-execute")
    def live_loopback_execute(
        release_json: str = typer.Option(..., "--release-json"),
        envelope_kind: str = typer.Option(..., "--envelope-kind"),
        envelope_json: str = typer.Option(..., "--envelope-json"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            release = LiveExecutorReleaseResult.model_validate_json(release_json)
            parsed_envelope = json.loads(envelope_json)
            if not isinstance(parsed_envelope, dict):
                raise ValueError("envelope must be a JSON object")
        except (JSONDecodeError, ValidationError, ValueError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_loopback_execute",
                    "error": str(exc),
                    "loopback_executed": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveLoopbackExecutorRuntime().execute(
            release=release,
            envelope_kind=envelope_kind,
            envelope=parsed_envelope,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
