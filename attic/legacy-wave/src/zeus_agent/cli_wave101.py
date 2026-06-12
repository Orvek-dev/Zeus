from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInResult


def register_wave101_commands(app: typer.Typer) -> None:
    @app.command("live-transport-activation-plan")
    def live_transport_activation_plan(
        opt_in_json: str = typer.Option(..., "--opt-in-json"),
        adapter_kind: str = typer.Option(..., "--adapter-kind"),
        adapter_plan_json: str = typer.Option(..., "--adapter-plan-json"),
        activation_ref: str = typer.Option(..., "--activation-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            opt_in = LiveTransportOptInResult.model_validate_json(opt_in_json)
            plan = _parse_adapter_plan(adapter_kind=adapter_kind, payload=adapter_plan_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_transport_activation_plan",
                    "error": str(exc),
                    "transport_activation_ready": False,
                    "live_transport_enabled": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveTransportActivationRuntime().plan(
            opt_in=opt_in,
            adapter_kind=adapter_kind,
            adapter_plan=plan,
            activation_ref=activation_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _parse_adapter_plan(adapter_kind: str, payload: str):
    if adapter_kind == "provider":
        return LiveProviderAdapterResult.model_validate_json(payload)
    if adapter_kind == "gateway":
        return LiveGatewayAdapterResult.model_validate_json(payload)
    return LiveMcpAdapterResult.model_validate_json(payload)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
