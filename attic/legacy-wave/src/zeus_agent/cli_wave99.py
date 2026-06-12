from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult


def register_wave99_commands(app: typer.Typer) -> None:
    @app.command("live-mcp-adapter-plan")
    def live_mcp_adapter_plan(
        release_json: str = typer.Option(..., "--release-json"),
        mcp_envelope_json: str = typer.Option(..., "--mcp-envelope-json"),
        transport_mode: str = typer.Option("dry_run", "--transport-mode"),
        timeout_ms: int = typer.Option(1500, "--timeout-ms"),
        retry_attempts: int = typer.Option(1, "--retry-attempts"),
        idempotency_key: str = typer.Option(..., "--idempotency-key"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            release = LiveExecutorReleaseResult.model_validate_json(release_json)
            envelope = LiveMcpRequestResult.model_validate_json(mcp_envelope_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_mcp_adapter_plan",
                    "error": str(exc),
                    "adapter_plan_ready": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveMcpAdapterRuntime().plan(
            release=release,
            mcp_envelope=envelope,
            transport_mode=transport_mode,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
            idempotency_key=idempotency_key,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
