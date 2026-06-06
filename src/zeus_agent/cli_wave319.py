from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.goal_intelligence_runtime import build_goal_intelligence_contract


def register_wave319_commands(app: typer.Typer) -> None:
    @app.command("goal-intelligence-runtime")
    def goal_intelligence_runtime(
        scenario: str = typer.Option("status", "--scenario"),
        home: Optional[Path] = typer.Option(None, "--home"),
        objective: str = typer.Option(
            "Help Zeus understand the user goal and choose a safe adaptive execution workflow.",
            "--objective",
        ),
        task_count: int = typer.Option(4, "--task-count"),
        requires_code: bool = typer.Option(False, "--requires-code"),
        requires_research: bool = typer.Option(False, "--requires-research"),
        risk_level: str = typer.Option("normal", "--risk-level"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        payload = build_goal_intelligence_contract(
            scenario=scenario,
            home=home,
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
        ).to_payload()
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
