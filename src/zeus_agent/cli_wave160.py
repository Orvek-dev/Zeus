from __future__ import annotations

import json

import typer
from pydantic import JsonValue

from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowRuntime


def register_wave160_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow")
    def live_research_workflow(
        query: str = typer.Option(..., "--query"),
        objective_id: str = typer.Option("live-research.objective", "--objective-id"),
        endpoint: list[str] = typer.Option([], "--endpoint", help="Endpoint override as adapter_id=url. Repeatable."),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        overrides, errors = _endpoint_overrides(endpoint)
        if errors:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": errors,
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowRuntime().compile_workflow(
            query=query,
            objective_id=objective_id,
            endpoint_overrides=overrides,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _endpoint_overrides(raw_values: list[str]) -> tuple[dict[str, str], list[str]]:
    overrides: dict[str, str] = {}
    errors: list[str] = []
    for raw in raw_values:
        if "=" not in raw:
            errors.append("live_research_workflow_endpoint_override_malformed")
            continue
        adapter_id, value = raw.split("=", 1)
        if adapter_id.strip() == "" or value.strip() == "":
            errors.append("live_research_workflow_endpoint_override_malformed")
            continue
        overrides[adapter_id.strip()] = value.strip()
    return overrides, errors


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
