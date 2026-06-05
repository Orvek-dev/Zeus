from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseResult
from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterRuntime
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult


def register_wave98_commands(app: typer.Typer) -> None:
    @app.command("live-gateway-adapter-plan")
    def live_gateway_adapter_plan(
        release_json: str = typer.Option(..., "--release-json"),
        gateway_envelope_json: str = typer.Option(..., "--gateway-envelope-json"),
        transport_mode: str = typer.Option("dry_run", "--transport-mode"),
        timeout_ms: int = typer.Option(1500, "--timeout-ms"),
        retry_attempts: int = typer.Option(1, "--retry-attempts"),
        idempotency_key: str = typer.Option(..., "--idempotency-key"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            release = LiveExecutorReleaseResult.model_validate_json(release_json)
            envelope = LiveGatewayDeliveryResult.model_validate_json(gateway_envelope_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_gateway_adapter_plan",
                    "error": str(exc),
                    "adapter_plan_ready": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveGatewayAdapterRuntime().plan(
            release=release,
            gateway_envelope=envelope,
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
