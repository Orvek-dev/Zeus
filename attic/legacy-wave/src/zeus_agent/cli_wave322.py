from __future__ import annotations

import json
from typing import Optional

import typer

from zeus_agent.cognitive_provider_activation_runtime import build_cognitive_provider_activation_contract


def register_wave322_commands(app: typer.Typer) -> None:
    @app.command("cognitive-provider-activation")
    def cognitive_provider_activation(
        scenario: str = typer.Option("status", "--scenario"),
        objective: str = typer.Option("제우스야, build a safe governed workflow from my objective.", "--objective"),
        provider_kind: str = typer.Option("fake", "--provider-kind"),
        operator_note: Optional[str] = typer.Option(None, "--operator-note"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_cognitive_provider_activation_contract(
            scenario=scenario,
            objective=objective,
            provider_kind=provider_kind,
            operator_note=operator_note,
        ).to_payload()
        if as_json:
            typer.echo(json.dumps(payload))
            return
        typer.echo(json.dumps(payload, indent=2))
