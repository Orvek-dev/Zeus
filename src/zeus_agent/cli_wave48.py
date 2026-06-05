from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError
from pydantic import JsonValue

from zeus_agent.orchestration_runtime import WorkflowCompileRequest
from zeus_agent.workflow_cockpit_runtime import WorkflowCockpitRuntime
from zeus_agent.workflow_learning_runtime import WorkflowCritiqueMemoryRuntime


def register_wave48_commands(app: typer.Typer) -> None:
    @app.command("workflow")
    def workflow(
        workflow_id: Optional[str] = typer.Option(None, "--workflow-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = WorkflowCockpitRuntime().build(workflow_id=workflow_id)
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("workflow-critique-memory-record")
    def workflow_critique_memory_record(
        objective: str = typer.Option(..., "--objective"),
        task_count: int = typer.Option(1, "--task-count"),
        requires_code: bool = typer.Option(False, "--requires-code"),
        requires_research: bool = typer.Option(False, "--requires-research"),
        risk_level: str = typer.Option("normal", "--risk-level"),
        evidence_target: str = typer.Option("mneme.wave203.workflow", "--evidence-target"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            request = WorkflowCompileRequest(
                objective=objective,
                task_count=task_count,
                requires_code=requires_code,
                requires_research=requires_research,
                risk_level=risk_level,
                evidence_target=evidence_target,
            )
        except ValidationError as exc:
            _print_payload({"decision": "blocked", "reason": "malformed_workflow_request", "error": str(exc)}, as_json=as_json)
            raise typer.Exit(code=1)
        result = WorkflowCritiqueMemoryRuntime(home or Path.cwd()).record(request=request)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
