from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanRuntime
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigResult


def register_wave157_commands(app: typer.Typer) -> None:
    @app.command("live-research-execution-plan")
    def live_research_execution_plan(
        source_config_json: str = typer.Option(..., "--source-config-json"),
        policy_json: str = typer.Option(..., "--policy-json"),
        execution_ref: str = typer.Option(..., "--execution-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            source_config = LiveResearchSourceConfigResult.model_validate_json(source_config_json)
            policy = LiveResearchActivationPolicyResult.model_validate_json(policy_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "execution_ref": execution_ref,
                    "blocked_reasons": ["malformed_live_research_execution_plan"],
                    "error": str(exc),
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchExecutionPlanRuntime().plan(
            source_config=source_config,
            policy=policy,
            execution_ref=execution_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
