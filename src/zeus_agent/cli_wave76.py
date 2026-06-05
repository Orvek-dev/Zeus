from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.secret_resolver_runtime import SecretResolverPlanRuntime


def register_wave76_commands(app: typer.Typer) -> None:
    @app.command("credentials")
    def credentials(
        bind: bool = typer.Option(False, "--bind", help="Write a reference-only credential binding proof."),
        resolver_plan: bool = typer.Option(False, "--resolver-plan", help="Build a reference-only secret resolver plan."),
        surface_kind: Optional[str] = typer.Option(None, "--surface-kind"),
        surface_id: Optional[str] = typer.Option(None, "--surface-id"),
        credential_scope: Optional[str] = typer.Option(None, "--credential-scope"),
        env_ref: Optional[str] = typer.Option(None, "--env-ref"),
        vault_ref: Optional[str] = typer.Option(None, "--vault-ref"),
        expected_endpoint: Optional[str] = typer.Option(None, "--expected-endpoint"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        zeus_home = home or default_zeus_home()
        runtime = CredentialReadinessRuntime(zeus_home)
        if bind:
            result = runtime.bind(
                surface_kind=surface_kind or "",
                surface_id=surface_id or "",
                credential_scope=credential_scope or "",
                env_ref=env_ref,
                vault_ref=vault_ref,
            )
            _print_payload(result.to_payload(), as_json=as_json)
            return
        if resolver_plan:
            result = SecretResolverPlanRuntime(zeus_home).plan(
                surface_kind=surface_kind or "",
                surface_id=surface_id or "",
                credential_scope=credential_scope,
                expected_endpoint=expected_endpoint,
            )
            _print_payload(result.to_payload(), as_json=as_json)
            return
        result = runtime.build()
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
