from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime


def register_wave140_commands(app: typer.Typer) -> None:
    @app.command("live-research-activation-policy")
    def live_research_activation_policy(
        source_id: str = typer.Option(..., "--source-id"),
        query: str = typer.Option(..., "--query"),
        live_search_requested: bool = typer.Option(False, "--live-search-requested"),
        approval_ref: Optional[str] = typer.Option(None, "--approval-ref"),
        source_pin_ref: Optional[str] = typer.Option(None, "--source-pin-ref"),
        max_results: int = typer.Option(5, "--max-results"),
        rate_limit_per_minute: int = typer.Option(30, "--rate-limit-per-minute"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = LiveResearchActivationPolicyRuntime().plan(
            source_id=source_id,
            query=query,
            live_search_requested=live_search_requested,
            approval_ref=approval_ref,
            source_pin_ref=source_pin_ref,
            max_results=max_results,
            rate_limit_per_minute=rate_limit_per_minute,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
