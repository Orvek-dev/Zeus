from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyRuntime
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult


def register_wave110_commands(app: typer.Typer) -> None:
    @app.command("live-remote-transport-policy")
    def live_remote_transport_policy(
        activation_json: str = typer.Option(..., "--activation-json"),
        adapter_kind: str = typer.Option(..., "--adapter-kind"),
        adapter_plan_json: str = typer.Option(..., "--adapter-plan-json"),
        transport_kind: str = typer.Option(..., "--transport-kind"),
        remote_target: str = typer.Option(..., "--remote-target"),
        allow_remote: list[str] = typer.Option([], "--allow-remote"),
        credential_scope: str = typer.Option(..., "--credential-scope"),
        credential_binding_ref: str = typer.Option(..., "--credential-binding-ref"),
        policy_ref: str = typer.Option(..., "--policy-ref"),
        audit_ref: str = typer.Option(..., "--audit-ref"),
        redaction_ref: str = typer.Option(..., "--redaction-ref"),
        teardown_ref: str = typer.Option(..., "--teardown-ref"),
        production_review_ref: str = typer.Option(..., "--production-review-ref"),
        resources_requested: bool = typer.Option(False, "--resources-requested"),
        prompts_requested: bool = typer.Option(False, "--prompts-requested"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            activation = LiveTransportActivationResult.model_validate_json(activation_json)
            adapter_plan = _adapter_plan(adapter_kind, adapter_plan_json)
        except (ValidationError, ValueError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_remote_transport_policy",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveRemoteTransportPolicyRuntime().plan(
            activation=activation,
            adapter_kind=adapter_kind,
            adapter_plan=adapter_plan,
            transport_kind=transport_kind,
            remote_target=remote_target,
            allowed_remote_targets=tuple(allow_remote),
            credential_scope=credential_scope,
            credential_binding_ref=credential_binding_ref,
            policy_ref=policy_ref,
            audit_ref=audit_ref,
            redaction_ref=redaction_ref,
            teardown_ref=teardown_ref,
            production_review_ref=production_review_ref,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _adapter_plan(adapter_kind: str, adapter_plan_json: str):
    if adapter_kind == "provider":
        return LiveProviderAdapterResult.model_validate_json(adapter_plan_json)
    if adapter_kind == "gateway":
        return LiveGatewayAdapterResult.model_validate_json(adapter_plan_json)
    if adapter_kind == "mcp":
        return LiveMcpAdapterResult.model_validate_json(adapter_plan_json)
    raise ValueError("unsupported_adapter_kind")


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
