from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.live_mcp_activation_policy_runtime import LiveMcpActivationPolicyRuntime


def register_wave139_commands(app: typer.Typer) -> None:
    @app.command("live-mcp-activation-policy")
    def live_mcp_activation_policy(
        server_id: str = typer.Option(..., "--server-id"),
        startup_requested: bool = typer.Option(False, "--startup-requested"),
        resources_requested: bool = typer.Option(False, "--resources-requested"),
        prompts_requested: bool = typer.Option(False, "--prompts-requested"),
        approval_ref: Optional[str] = typer.Option(None, "--approval-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveMcpActivationPolicyRuntime().plan(
            server_id=server_id,
            startup_requested=startup_requested,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
            approval_ref=approval_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
