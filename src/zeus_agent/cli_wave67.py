from __future__ import annotations

from typing import Optional

import typer

from zeus_agent.work_entry_runtime import WorkEntryRuntime


def register_wave67_commands(app: typer.Typer) -> None:
    @app.command("work")
    def work(
        objective: str = typer.Option(..., "--objective", "-o", help="Objective to compile into a Zeus work plan."),
        task_count: int = typer.Option(1, "--task-count", help="Estimated task count for workflow selection."),
        requires_code: bool = typer.Option(False, "--requires-code", help="Mark the objective as code-changing."),
        requires_research: bool = typer.Option(False, "--requires-research", help="Mark the objective as research-heavy."),
        risk_level: str = typer.Option("normal", "--risk-level", help="Risk level: low, normal, or high."),
        evidence_target: str = typer.Option("mneme.work.entry", "--evidence-target"),
        surface_id: Optional[str] = typer.Option(None, "--surface-id", help="Optional live surface profile for dry-run preview."),
        principal_id: str = typer.Option("local.operator", "--principal-id"),
        delivery_target: Optional[str] = typer.Option(None, "--delivery-target"),
        allowlisted_delivery_target: list[str] = typer.Option(
            [],
            "--allowlisted-delivery-target",
            help="Allowlisted delivery target for gateway live dry-run preview. Repeatable.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        payload = WorkEntryRuntime().plan(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=evidence_target,
            surface_id=surface_id,
            principal_id=principal_id,
            delivery_target=delivery_target,
            allowlisted_delivery_targets=tuple(allowlisted_delivery_target),
        ).to_payload()
        _print_payload(payload, as_json)


def _print_payload(payload: dict[str, object], as_json: bool) -> None:
    import json

    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
