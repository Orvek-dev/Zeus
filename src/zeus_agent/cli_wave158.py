from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanResult
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeRuntime


def register_wave158_commands(app: typer.Typer) -> None:
    @app.command("live-research-loopback-smoke")
    def live_research_loopback_smoke(
        plan_json: str = typer.Option(..., "--plan-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            plan = LiveResearchExecutionPlanResult.model_validate_json(plan_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_loopback_smoke"],
                    "error": str(exc),
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchLoopbackSmokeRuntime().execute(plan=plan)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
