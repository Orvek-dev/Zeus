from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofResult
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime


def register_wave100_commands(app: typer.Typer) -> None:
    @app.command("live-transport-opt-in")
    def live_transport_opt_in(
        adapter_kind: str = typer.Option(..., "--adapter-kind"),
        adapter_plan_json: str = typer.Option(..., "--adapter-plan-json"),
        operator_proof_json: str = typer.Option(..., "--operator-proof-json"),
        opt_in_ref: str = typer.Option(..., "--opt-in-ref"),
        requested_transport_mode: str = typer.Option("live", "--requested-transport-mode"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            plan = _parse_adapter_plan(adapter_kind=adapter_kind, payload=adapter_plan_json)
            proof = LiveOperatorProofResult.model_validate_json(operator_proof_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_transport_opt_in",
                    "error": str(exc),
                    "live_transport_opted_in": False,
                    "live_transport_enabled": False,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveTransportOptInRuntime().record(
            adapter_kind=adapter_kind,
            adapter_plan=plan,
            operator_proof=proof,
            opt_in_ref=opt_in_ref,
            requested_transport_mode=requested_transport_mode,
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
